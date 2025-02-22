import time
from r2a.ir2a import IR2A
from player.parser import *

class r2a_Ingrid(IR2A):
    def __init__(self, identifier: int):
        """Inicializa a classe r2a_Ingrid para adaptação de streaming adaptativo.

        Parâmetros:
        identifier (int): Identificador único da instância.
        """
        super().__init__(identifier)
        
        self.max_throughput_records = 5  # Quantidade máxima de registros de throughput armazenados
        self.recent_throughputs = []  # Lista para armazenar valores recentes de throughput
        self.request_start_time = 0  # Marca o tempo da última requisição
        self.quality_options = []  # Armazena os níveis de qualidade disponíveis
        self.active_quality_level = 0  # Indica a qualidade de vídeo em uso
        self.segment_size_manager = Adaptive_Segment_Manager(self.max_throughput_records)  # Instância do gerenciador de segmentos

    def process_xml_transaction(self, xml_message):
        """Processa a requisição XML e encaminha para o próximo nível.

        Parâmetros:
        xml_message: Dados da requisição XML.
        """
        if xml_message is not None:
            current_time = time.time()  # Mede o tempo atual
            self.request_start_time = current_time  # Atualiza o tempo da última requisição
            self.send_down(xml_message)  # Encaminha a mensagem para processamento

    def process_xml_response(self, xml_data):
        """Processa a resposta XML e atualiza os valores de throughput e qualidade.

        Parâmetros:
        xml_data: Dados da resposta XML contendo informações do MPD.
        """
        # Faz o parsing da resposta XML
        mpd_data = parse_mpd(xml_data.get_payload())  
        self.quality_options = mpd_data.get_qi()  # Atualiza os níveis de qualidade disponíveis
        
        # Calcula o tempo decorrido desde a requisição
        elapsed_time = time.time() - self.request_start_time  
        if elapsed_time > 0:  # Evita divisão por zero
            calculated_throughput = xml_data.get_bit_length() / elapsed_time
            self.add_throughput_record(calculated_throughput)  # Armazena o novo throughput
        
        # Encaminha a mensagem para o próximo nível
        self.send_up(xml_data)

    def process_segment_size_request(self, segment_request):
        """Processa a solicitação de tamanho do segmento e ajusta a qualidade.

        Parâmetros:
        segment_request: Mensagem contendo a solicitação do segmento.
        """
        # Marca o tempo da requisição
        self.request_start_time = time.time()

        # Atualiza a lista de throughput no gerenciador de qualidade
        self.segment_size_manager.update_throughput_history(self.recent_throughputs)

        # Determina a nova qualidade com base na adaptação
        selected_quality_index = self.segment_size_manager.update_quality(self.active_quality_level, self.quality_options)

        # Atualiza a qualidade ativa
        self.active_quality_level = selected_quality_index

        # Adiciona o identificador da qualidade ao segmento solicitado
        if 0 <= selected_quality_index < len(self.quality_options):
            segment_request.add_quality_id(self.quality_options[selected_quality_index])

        # Encaminha a solicitação para o próximo nível
        self.send_down(segment_request)

    def process_segment_size_response(self, segment_response):
        """Processa a resposta do tamanho do segmento e atualiza throughput.

        Parâmetros:
        segment_response: Mensagem contendo informações sobre o segmento.
        """
        # Calcula o tempo decorrido desde a requisição
        elapsed_time = time.time() - self.request_start_time  

        # Garante que o tempo decorrido não seja zero para evitar erro matemático
        if elapsed_time > 0:
            calculated_throughput = segment_response.get_bit_length() / elapsed_time
            self.add_throughput_record(calculated_throughput)  # Registra novo throughput

        # Encaminha a resposta para o próximo nível
        self.send_up(segment_response)

    def add_throughput_record(self, new_value: float):
        """Adiciona um novo valor de throughput, mantendo o histórico atualizado.

        Parâmetros:
        new_value (float): Novo valor de throughput medido.
        """
        if len(self.recent_throughputs) >= self.max_throughput_records:
            self.recent_throughputs.pop(0)  # Remove o valor mais antigo para manter o tamanho da lista
        self.recent_throughputs.append(new_value)

    def initialize_system_resources(self):
    #Inicializa os recursos necessários para o funcionamento do sistema.
     self.request_start_time = 0  # Garante que o tempo da requisição inicie corretamente
     self.recent_throughputs.clear()  # Limpa o histórico de throughputs caso tenha valores antigos
     self.active_quality_level = 0  # Define a qualidade inicial como a mais baixa disponível
     print("Sistema inicializado. Recursos prontos para uso.")  # Log simples para depuração

    def release_allocated_resources(self):
    #Libera recursos e redefine variáveis para evitar consumo desnecessário de memória.
     self.request_start_time = None  # Marca que não há requisições pendentes
     self.recent_throughputs = []  # Esvazia a lista de valores de throughput
     self.active_quality_level = None  # Remove a referência à qualidade ativa
     print("Recursos liberados. Sistema pronto para encerramento.")  # Log simples para depuração


from collections import deque

class Adaptive_Segment_Manager:
    def __init__(self, max_throughput_records: int):
        """Initializes the adaptive segment manager.

        Parameters:
        max_throughput_records (int): Maximum number of stored throughput records.
        """
        self.maximum_throughput_records = max_throughput_records  # Keeping consistency with r2a_Ingrid
        self.throughput_records = deque(maxlen=max_throughput_records)  # List of throughput records
        self.throughput_mean = 0  # Mean throughput value
        self.throughput_variability = 0  # Variability in throughput

    def update_throughput_history(self, recent_throughput_values):
        """Updates the throughput history.

        Parameters:
        recent_throughput_values (list): List containing recent throughput values.
        """
        self.throughput_records.clear()
        self.throughput_records.extend(recent_throughput_values)
        self.calculate_mean_and_variability()

    def calculate_mean_and_variability(self):
        """Calculates the mean (throughput_mean) and variability (throughput_variability) of the stored throughput."""
        if not self.throughput_records:
            self.throughput_mean = 0
            self.throughput_variability = 0
            return
        
        self.throughput_mean = sum(self.throughput_records) / len(self.throughput_records)
        self.throughput_variability = sum((value - self.throughput_mean) ** 2 for value in self.throughput_records) / len(self.throughput_records)

    def calculate_probability(self):
        """Calculates probability based on throughput variability."""
        weighted_variability = self.throughput_variability  # Uses calculated variability
        probability = self.throughput_mean / (self.throughput_mean + weighted_variability) if (self.throughput_mean + weighted_variability) != 0 else 0  # Prevents division by zero
        print(f"Probability: {probability:.4f}\n")
        return probability

    def calculate_tau_and_theta(self, current_quality_level: int, quality_levels: list):
        """Calculates tau and theta values for video quality adjustment.

        Parameters:
        current_quality_level (int): Current quality index.
        quality_levels (list): List of available quality levels.

        Returns:
        tuple: Values of tau and theta.
        """
        probability = self.calculate_probability()

        # Calculation of tau and theta as described in the article
        tau_value = (1 - probability) * (current_quality_level - quality_levels[max(0, current_quality_level - 1)])  # Approaches previous level
        theta_value = probability * (quality_levels[min(len(quality_levels) - 1, current_quality_level + 1)] - current_quality_level)  # Approaches next level

        print(f"Tau: {tau_value:.4f}\n")
        print(f"Theta: {theta_value:.4f}\n")

        return tau_value, theta_value

    def update_video_quality(self, current_quality_level: int, quality_level_list: list):
        """Updates video quality based on tau and theta calculations.

        Parameters:
        current_quality_level (int): Current quality index.
        quality_level_list (list): List of available quality levels.

        Returns:
        int: Updated quality index.
        """
        if not quality_level_list:
            return current_quality_level  # If list is empty, maintain current quality

        quality_level_indices = list(range(len(quality_level_list)))  # Generate a list of quality indices
        tau_value, theta_value = self.calculate_tau_and_theta(current_quality_level, quality_level_indices)

        # Determine new quality based on tau and theta
        updated_quality_level = round(current_quality_level - tau_value + theta_value)  # Adjusts to the nearest valid value
        updated_quality_level = max(0, min(len(quality_level_list) - 1, updated_quality_level))  # Ensures it stays within valid limits

        return updated_quality_level

    def update_throughput_list(self, new_throughput_list: list):
        """Updates the throughput list and recalculates statistical parameters.

        Parameters:
        new_throughput_list (list): New list of throughput values.
        """
        self.throughput_records = deque(new_throughput_list, maxlen=self.maximum_throughput_records)
        self.total_records = len(self.throughput_records)
        self.throughput_mean = sum(self.throughput_records) / self.total_records if self.total_records > 0 else 0  # Prevents division by zero
        print(f"Updated throughput list: {self.throughput_records}\n")
