import json
import os
import socket
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
HOST = "127.0.0.1"
PORT = 8300  # Porta do Servidor C Executor
INITIAL_CODE_FILE = "main.go"

# ----------------------------------------------------------------------
# --- Thread de Comunicação TCP (Worker) ---
# A lógica TCP é mantida, garantindo que a GUI não congele.
# ----------------------------------------------------------------------


class TcpWorker(QThread):
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, code_content: str):
        super().__init__()
        self.code_content = code_content

    def run(self):
        """Executa a lógica de comunicação TCP (simulando o client.c)."""

        response_data = {}

        try:
            # 1. Escapar e montar a payload JSON
            # Garante que backslashes, novas linhas e aspas sejam escapados.
            escaped_code = (
                self.code_content.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace('"', '\\"')
            )

            tcp_payload = f'{{"code":"{escaped_code}"}}\n'

            # 2. Criar e Conectar o Socket
            with socket.create_connection((HOST, PORT), timeout=10) as conn:
                conn.sendall(tcp_payload.encode("utf-8"))

                # 3. Receber a Resposta
                response_bytes = conn.recv(4096)

                if not response_bytes:
                    self.error_signal.emit(
                        "Servidor C fechou a conexão ou não enviou resposta."
                    )
                    return

                response_json = response_bytes.decode("utf-8").strip()

                # 4. Decodificar a resposta do C Server
                response_data = json.loads(response_json)

        except socket.timeout:
            self.error_signal.emit(
                "ERRO: Tempo limite (timeout) atingido ao conectar ou ler do servidor."
            )
            return
        except ConnectionRefusedError:
            self.error_signal.emit(
                f"ERRO: Conexão recusada em {HOST}:{PORT}. O Servidor C está rodando?"
            )
            return
        except json.JSONDecodeError:
            self.error_signal.emit(
                f"ERRO: Resposta inválida (JSON corrompido) recebida: {response_json}"
            )
            return
        except Exception as e:
            self.error_signal.emit(f"ERRO inesperado na comunicação TCP: {str(e)}")
            return

        self.result_signal.emit(response_data)


# ----------------------------------------------------------------------
# --- Aplicação Principal PyQt6 ---
# ----------------------------------------------------------------------


class ExecutorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Executor de Código Go Remoto (PyQt6)")
        self.setGeometry(100, 100, 1000, 800)

        self.worker = None
        self.load_initial_code()
        self.init_ui()

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
        editor_group = QGroupBox("Código Fonte Go")
        editor_layout = QVBoxLayout(editor_group)

        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Consolas", 12))
        self.code_editor.setText(self.initial_code)

        # Estilo para o editor de código
        self.code_editor.setStyleSheet(
            "background-color: #2e2e2e; color: #ffffff; border: 1px solid #555555;"
        )

        editor_layout.addWidget(self.code_editor)

        self.send_button = QPushButton("Enviar e Executar")
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
        error_box = QGroupBox("Erro de Compilação/Execução (Stderr)")
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
        self.error_output.setText("Conectando e enviando código... Por favor, aguarde.")
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
        output = result_dict.get("output", "").replace("\\n", "\n")
        error_msg = result_dict.get("error", "").replace("\\n", "\n")

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

        self.error_output.setText(f"ERRO DE COMUNICAÇÃO:\n{error_message}")
        self.error_output.setStyleSheet(
            "background-color: #ffcccc; color: #880000; border: 1px solid #ff0000;"
        )
        self.stdout_output.setText(
            "Não foi possível conectar ao servidor C. Verifique o status da porta 8400."
        )


if __name__ == "__main__":
    # Garante que o arquivo de código inicial exista
    if not os.path.exists(INITIAL_CODE_FILE):
        with open(INITIAL_CODE_FILE, "w") as f:
            f.write(
                'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Initial setup!")\n}'
            )

    app = QApplication(sys.argv)
    window = ExecutorGUI()
    window.show()
    sys.exit(app.exec())
