import json
import os
import socket
import subprocess  # Novo módulo para executar o client.c
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --- Configurações de Comunicação ---
# HOST e PORT não são mais usados pelo TcpWorker (agora são internos ao client.c)
HOST = "localhost"  # Mantido apenas para contexto da GUI
PORT = 8300  # Mantido apenas para contexto da GUI
INITIAL_CODE_FILE = "main.go"
CLIENT_EXECUTABLE = "./client"  # Nome do executável C

# ----------------------------------------------------------------------
# --- Thread de Comunicação TCP (Worker) ---
# A lógica TCP foi substituída pela execução do client.c
# ----------------------------------------------------------------------


class TcpWorker(QThread):
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, code_content: str):
        super().__init__()
        self.code_content = code_content

    def run(self):
        """Executa o cliente C para se comunicar com o servidor C."""

        # 1. Salvar o código no arquivo main.go
        try:
            with open(INITIAL_CODE_FILE, "w") as f:
                f.write(self.code_content)
        except Exception as e:
            self.error_signal.emit(
                f"ERRO: Não foi possível escrever em {INITIAL_CODE_FILE}: {str(e)}"
            )
            return

        # 2. Verificar se o cliente C existe
        if not os.path.exists(CLIENT_EXECUTABLE):
            self.error_signal.emit(
                f"ERRO: O executável do cliente C não foi encontrado em {CLIENT_EXECUTABLE}. Compile o client.c primeiro."
            )
            return

        response_data = {}

        try:
            # 3. Executar o cliente C
            # A saída padrão do cliente C será capturada (stdout).
            # O cliente C é responsável por conectar, enviar o código e receber a resposta JSON.

            # Executamos o cliente e esperamos ele terminar.
            result = subprocess.run(
                [CLIENT_EXECUTABLE],
                capture_output=True,  # Captura stdout e stderr
                text=True,  # Decodifica a saída como texto
                timeout=15,  # Define um tempo limite para a execução do cliente C
            )

            # A saída do cliente C (stdout) contém mensagens de log E a resposta JSON.
            # A resposta JSON é a última coisa que o cliente C imprime.

            # O JSON de resposta deve estar na saída final do cliente C.
            # O cliente C imprime a resposta JSON entre as linhas de separação:
            # ============== RESULTADO DO SERVIDOR ==============
            # {"output": "...", "error": "..."}\n
            # =================================================

            # Vamos procurar a resposta JSON no stdout
            stdout_lines = result.stdout.strip().split("\n")

            response_json = ""
            start_capture = False
            for line in stdout_lines:
                if "============== RESULTADO DO SERVIDOR ==============" in line:
                    start_capture = True
                    continue
                if "=================================================" in line:
                    break
                if start_capture and line.strip():
                    response_json = line.strip()
                    break  # O JSON é a próxima linha após o separador

            if not response_json:
                # Se não encontrou o JSON, considera a saída completa como erro de comunicação
                error_details = result.stdout + "\n" + result.stderr
                self.error_signal.emit(
                    f"ERRO: Não foi possível obter o JSON de resposta do cliente C.\nDetalhes da Execução do Cliente C:\n{error_details}"
                )
                return

            # 4. Decodificar a resposta do C Server
            response_data = json.loads(response_json)

        except subprocess.TimeoutExpired:
            self.error_signal.emit(
                "ERRO: Tempo limite (timeout) atingido ao executar o cliente C."
            )
            return
        except FileNotFoundError:
            self.error_signal.emit(
                f"ERRO: O executável do cliente C não foi encontrado em {CLIENT_EXECUTABLE}."
            )
            return
        except json.JSONDecodeError:
            self.error_signal.emit(
                f"ERRO: Resposta inválida (JSON corrompido) recebida do cliente C: {response_json}"
            )
            return
        except Exception as e:
            self.error_signal.emit(
                f"ERRO inesperado na execução do cliente C: {str(e)}"
            )
            return

        self.result_signal.emit(response_data)


# ----------------------------------------------------------------------
# O restante do código da classe ExecutorGUI e o bloco __main__ permanecem inalterados.
# A única exceção é o bloco __main__ que deve garantir que o cliente C seja compilado.
# ----------------------------------------------------------------------


class ExecutorGUI(QMainWindow):
    # ... (o método __init__ e load_initial_code permanecem os mesmos)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Executor de Código Go Remoto (PyQt6 - Cliente C)")
        self.setGeometry(100, 100, 1000, 800)

        self.worker = None
        self.load_initial_code()
        self.init_ui()

    # ... (o método init_ui e reset_output_boxes permanecem os mesmos)

    def load_initial_code(self):
        """Carrega o código Go inicial, criando o arquivo se não existir."""
        try:
            with open(INITIAL_CODE_FILE, "r") as f:
                self.initial_code = f.read()
        except FileNotFoundError:
            self.initial_code = 'package main\n\nimport "fmt"\n\nfunc main() {\n\t// Edite seu código aqui\n\tfmt.Println("Execução bem-sucedida!")\n}'

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # 1. --- Área de Edição e Botão (Agrupado) ---
        editor_group = QGroupBox("Código Fonte Go (Lido por C)")
        editor_layout = QVBoxLayout(editor_group)

        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Consolas", 12))
        self.code_editor.setText(self.initial_code)

        # Estilo para o editor de código
        self.code_editor.setStyleSheet(
            "background-color: #2e2e2e; color: #ffffff; border: 1px solid #555555;"
        )

        editor_layout.addWidget(self.code_editor)

        self.send_button = QPushButton("Enviar e Executar (via Cliente C)")
        self.send_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.send_button.setStyleSheet(
            "background-color: #007bff; color: white; padding: 10px; border-radius: 5px;"
        )
        self.send_button.clicked.connect(self.start_execution)
        editor_layout.addWidget(self.send_button)

        main_layout.addWidget(editor_group, 2)  # Fator de alongamento 2

        # 2. --- Área de Saída (Divisão Horizontal) ---
        output_group = QGroupBox("Resultados da Execução no Servidor")
        output_layout = QHBoxLayout(output_group)

        # 2.1. Caixa de Saída Padrão (Stdout)
        stdout_box = QGroupBox("Saída Padrão (Stdout)")
        stdout_layout = QVBoxLayout(stdout_box)

        self.stdout_output = QTextEdit()
        self.stdout_output.setReadOnly(True)
        self.stdout_output.setFont(QFont("Consolas", 10))
        self.stdout_output.setStyleSheet(
            "background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;"
        )
        self.stdout_output.setText("Aguardando execução...")

        stdout_layout.addWidget(self.stdout_output)
        output_layout.addWidget(stdout_box, 1)  # Fator de alongamento 1

        # 2.2. Caixa de Erro (Stderr)
        error_box = QGroupBox("Erro de Compilação/Execução (Stderr/Comunicação)")
        error_layout = QVBoxLayout(error_box)

        self.error_output = QTextEdit()
        self.error_output.setReadOnly(True)
        self.error_output.setFont(QFont("Consolas", 10))
        self.error_output.setStyleSheet(
            "background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;"
        )

        error_layout.addWidget(self.error_output)
        output_layout.addWidget(error_box, 1)  # Fator de alongamento 1

        main_layout.addWidget(output_group, 1)  # Fator de alongamento 1

        self.setCentralWidget(central_widget)

    def reset_output_boxes(self):
        """Limpa as caixas de saída e define o estilo padrão."""
        self.stdout_output.setText("")
        self.error_output.setText("")
        # Restaura os estilos padrão
        self.stdout_output.setStyleSheet(
            "background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;"
        )
        self.error_output.setStyleSheet(
            "background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;"
        )

    def start_execution(self):
        """Inicia a thread worker para executar o código."""
        self.send_button.setEnabled(False)
        self.reset_output_boxes()
        self.error_output.setText(
            "Executando cliente C para enviar o código... Por favor, aguarde."
        )
        self.error_output.setStyleSheet(
            "background-color: #ffffcc; color: black; border: 1px solid #cccc00;"
        )

        code = self.code_editor.toPlainText()

        self.worker = TcpWorker(code)
        self.worker.result_signal.connect(self.handle_result)
        self.worker.error_signal.connect(self.handle_error)
        self.worker.start()

    def handle_result(self, result_dict: dict):
        """Recebe o resultado de sucesso da thread e atualiza a GUI."""
        self.send_button.setEnabled(True)
        self.reset_output_boxes()

        # Desescapa os caracteres de nova linha e aspas
        output = result_dict.get("output", "").replace("\\n", "\n").replace('\\"', '"')
        error_msg = (
            result_dict.get("error", "").replace("\\n", "\n").replace('\\"', '"')
        )

        # 1. Lógica de Erro (Stderr)
        if error_msg:
            self.error_output.setText(error_msg)
            self.stdout_output.setText("Execução falhou. Verifique a caixa de erro.")
        else:
            self.error_output.setText(
                "Nenhum erro de compilação ou execução reportado."
            )

        # 2. Lógica de Saída Padrão (Stdout)
        self.stdout_output.setText(output)

    def handle_error(self, error_message: str):
        """Recebe erros de comunicação da thread e atualiza a GUI."""
        self.send_button.setEnabled(True)
        self.reset_output_boxes()

        self.error_output.setText(f"ERRO DE EXECUÇÃO/COMUNICAÇÃO:\n{error_message}")
        self.error_output.setStyleSheet(
            "background-color: #ffcccc; color: #880000; border: 1px solid #ff0000;"
        )
        self.stdout_output.setText(
            "A execução do cliente C falhou. Verifique a caixa de erro para detalhes."
        )


if __name__ == "__main__":
    # Garante que o arquivo de código inicial exista
    if not os.path.exists(INITIAL_CODE_FILE):
        with open(INITIAL_CODE_FILE, "w") as f:
            f.write(
                'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Initial setup!")\n}'
            )

    # Passo de compilação (necessário)
    try:
        # Tenta compilar o cliente C antes de iniciar a GUI
        print(f"Compilando {CLIENT_EXECUTABLE}...")
        compile_result = subprocess.run(
            [
                "gcc",
                "client.c",
                "-o",
                CLIENT_EXECUTABLE,
                "-lncurses",
                "-lm",
                "-lpthread",
            ],
            capture_output=True,
            text=True,
        )
        if compile_result.returncode != 0:
            print("====================================")
            print("ERRO DE COMPILAÇÃO DO CLIENTE C:")
            print(compile_result.stderr)
            print("====================================")
            # Saímos se a compilação falhar, pois o cliente C é essencial
            sys.exit(1)
        else:
            print(
                f"Compilação de client.c bem-sucedida. Executável: {CLIENT_EXECUTABLE}"
            )

    except FileNotFoundError:
        print(
            "ERRO: O comando 'gcc' não foi encontrado. Certifique-se de que o compilador C está instalado."
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    window = ExecutorGUI()
    window.show()
    sys.exit(app.exec())
