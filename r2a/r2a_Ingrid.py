"""
UnB - Universidade de Brasilia  
Departamento de Ciência da Computação
CIC0124 - Redes de Computadores
Trabalho Algoritmo Seleção Dinâmica do Tamanho de Segmentos em Streaming Adaptativo HTTP
Autora: Ingrid Alves Rocha 
Matrícula: 202045348
"""

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

    def handle_xml_request(self, msg):
        """Processa a requisição XML e encaminha para o próximo nível.

        Parâmetros:
        msg: Dados da requisição XML.
        """
        if msg is not None:
            current_time = time.time()
            self.request_start_time = current_time
            self.send_down(msg)

    def handle_xml_response(self, msg):
        """Processa a resposta XML e atualiza os valores de throughput e qualidade.

        Parâmetros:
        msg: Dados da resposta XML contendo informações do MPD.
        """
        mpd_data = parse_mpd(msg.get_payload())  
        self.quality_options = mpd_data.get_qi()
        
        elapsed_time = time.time() - self.request_start_time
        if elapsed_time > 0:
            calculated_throughput = msg.get_bit_length() / elapsed_time
            self.add_throughput_record(calculated_throughput)

        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        """Processa a solicitação de tamanho do segmento e ajusta a qualidade.

        Parâmetros:
        msg: Mensagem contendo a solicitação do segmento.
        """
        self.request_start_time = time.time()
        self.segment_size_manager.update_throughput_history(self.recent_throughputs)
        selected_quality_index = self.segment_size_manager.update_video_quality(self.active_quality_level, self.quality_options)
        self.active_quality_level = selected_quality_index

        if 0 <= selected_quality_index < len(self.quality_options):
            msg.add_quality_id(self.quality_options[selected_quality_index])

        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        """Processa a resposta do tamanho do segmento e atualiza throughput.

        Parâmetros:
        msg: Mensagem contendo informações sobre o segmento.
        """
        elapsed_time = time.time() - self.request_start_time

        if elapsed_time > 0:
            calculated_throughput = msg.get_bit_length() / elapsed_time
            self.add_throughput_record(calculated_throughput)

        self.send_up(msg)

    def add_throughput_record(self, new_value: float):
        """Adiciona um novo valor de throughput, mantendo o histórico atualizado.

        Parâmetros:
        new_value (float): Novo valor de throughput medido.
        """
        if len(self.recent_throughputs) >= self.max_throughput_records:
            self.recent_throughputs.pop(0)
        self.recent_throughputs.append(new_value)

    def initialize(self):
        """Inicializa os recursos necessários para o funcionamento do sistema."""
        super().initialize()
        self.request_start_time = 0
        self.recent_throughputs.clear()
        self.active_quality_level = 0
        print("Sistema inicializado. Recursos prontos para uso.")

    def finalization(self):
        """Libera recursos e redefine variáveis para evitar consumo desnecessário de memória."""
        super().finalization()
        self.request_start_time = None
        self.recent_throughputs = []
        self.active_quality_level = None
        print("Recursos liberados. Sistema pronto para encerramento.")



from collections import deque

class Adaptive_Segment_Manager:
    def __init__(self, max_throughput_records: int):
        """Inicializa o gerenciador de segmentos adaptativos.

        Parâmetros:
        max_throughput_records (int): Número máximo de registros de throughput armazenados.
        """
        self.maximum_throughput_records = max_throughput_records  # Keeping consistency with r2a_Ingrid
        self.throughput_records = deque(maxlen=max_throughput_records)  # List of throughput records
        self.throughput_mean = 0  # Mean throughput value
        self.throughput_variability = 0  # Variability in throughput

    def update_throughput_history(self, recent_throughput_values):
        """"Limpa os registros anteriores e adiciona novos valores de throughput.
        
        Parâmetros:
        recent_throughput_values (list): Lista contendo os novos valores de throughput.
        """
        self.throughput_records.clear()
        self.throughput_records.extend(recent_throughput_values)
        self.calculate_mean_and_variability()

    def calculate_mean_and_variability(self):
        """"Calcula a média (throughput_mean) e a variabilidade (throughput_variability) dos valores armazenados."""
        if not self.throughput_records:
            self.throughput_mean = 0
            self.throughput_variability = 0
            return
        
        self.throughput_mean = sum(self.throughput_records) / len(self.throughput_records)
        self.throughput_variability = sum((value - self.throughput_mean) ** 2 for value in self.throughput_records) / len(self.throughput_records)

    def calculate_probability(self):
        """Calcula a probabilidade com base na variabilidade do throughput."""
        weighted_variability = self.throughput_variability  # Usa a variabilidade calculada
        probability = self.throughput_mean / (self.throughput_mean + weighted_variability) if (self.throughput_mean + weighted_variability) != 0 else 0  # Prevents division by zero
        print(f"Probability: {probability:.4f}\n")
        return probability

    def calculate_tau_and_theta(self, current_quality_level: int, quality_levels: list):
        """Calcula os valores de tau e theta para ajuste da qualidade do vídeo.

        Parâmetros:
        current_quality_level (int): Índice da qualidade atual.
        quality_levels (list): Lista dos níveis de qualidade disponíveis.

        Retorna:
        tuple: Valores de tau e theta.
        """
        probability = self.calculate_probability()

        # Cálculo de tau e theta conforme descrito no artigo
        tau_value = (1 - probability) * (current_quality_level - quality_levels[max(0, current_quality_level - 1)])  # Approaches previous level
        theta_value = probability * (quality_levels[min(len(quality_levels) - 1, current_quality_level + 1)] - current_quality_level)  # Approaches next level

        print(f"Tau: {tau_value:.4f}\n")
        print(f"Theta: {theta_value:.4f}\n")

        return tau_value, theta_value

    def update_video_quality(self, current_quality_level: int, quality_level_list: list):
        """Atualiza a qualidade do vídeo com base nos cálculos de tau e theta.

        Parâmetros:
        current_quality_level (int): Índice da qualidade atual.
        quality_level_list (list): Lista dos níveis de qualidade disponíveis.

        Retorna:
        int: Índice atualizado de qualidade.
        """
        if not quality_level_list:
            return current_quality_level  # Se a lista estiver vazia, mantém a qualidade atual

        quality_level_indices = list(range(len(quality_level_list)))  # Gera uma lista de índices de qualidade
        tau_value, theta_value = self.calculate_tau_and_theta(current_quality_level, quality_level_indices)

        updated_quality_level = round(current_quality_level - tau_value + theta_value)  # Ajusta para o valor válido mais próximo
        updated_quality_level = max(0, min(len(quality_level_list) - 1, updated_quality_level))  # Garante que o valor esteja dentro dos limites válidos

        return updated_quality_level

    def update_throughput_list(self, new_throughput_list: list):
        """Atualiza a lista de registros de throughput com novos valores.
        
        Parâmetros:
        new_throughput_list (list): Lista contendo os novos valores de throughput.
        """
        self.throughput_records = deque(new_throughput_list, maxlen=self.maximum_throughput_records)
        self.total_records = len(self.throughput_records)
        self.throughput_mean = sum(self.throughput_records) / self.total_records if self.total_records > 0 else 0   # Previne divisão por zero
        print(f"Updated throughput list: {self.throughput_records}\n")
