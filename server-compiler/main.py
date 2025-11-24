import json
import os
import re
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# --- Configurações ---
# Nome do arquivo inicial que será carregado/editado
INITIAL_CODE_FILE = "main.go"
# Nome do arquivo temporário que será enviado ao servidor via cliente C
TEMP_SEND_FILE = "code_to_send.go"
# Caminho para o executável do cliente C
CLIENT_EXECUTABLE = "./client"


class RemoteExecutorApp:
    def __init__(self, master):
        self.master = master
        master.title("Executor de Código Go Remoto (Cliente C)")

        # Variável para armazenar o código de teste
        self.code_content = self.load_initial_code()

        # --- Configuração da Interface ---
        self.setup_ui()

    def setup_ui(self):
        # 1. Área de Edição de Código
        code_frame = tk.LabelFrame(
            self.master,
            text=f"Código Go ({INITIAL_CODE_FILE} - Clique em Salvar antes de Enviar)",
            padx=10,
            pady=10,
        )
        code_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.code_text = scrolledtext.ScrolledText(
            code_frame, wrap=tk.WORD, width=80, height=20, font=("Consolas", 12)
        )
        self.code_text.insert(tk.INSERT, self.code_content)
        self.code_text.pack(fill="both", expand=True)

        # 2. Botões de Ação
        button_frame = tk.Frame(self.master)
        button_frame.pack(pady=5)

        self.save_button = tk.Button(
            button_frame, text="1. Salvar Código", command=self.save_code, bg="#ADD8E6"
        )
        self.save_button.pack(side=tk.LEFT, padx=10)

        self.send_button = tk.Button(
            button_frame,
            text="2. Enviar e Executar (via Client C)",
            command=self.send_code,
            bg="#90EE90",
        )
        self.send_button.pack(side=tk.LEFT, padx=10)

        # 3. Área de Resultado
        result_frame = tk.LabelFrame(
            self.master, text="Resultado e Erros do Servidor", padx=10, pady=5
        )
        result_frame.pack(padx=10, pady=5, fill="x")

        self.result_text = scrolledtext.ScrolledText(
            result_frame,
            wrap=tk.WORD,
            width=80,
            height=10,
            font=("Consolas", 10),
            state=tk.DISABLED,
            bg="#F0F0F0",
        )
        self.result_text.pack(fill="x")

    def load_initial_code(self):
        """Carrega o código Go inicial do arquivo."""
        try:
            with open(INITIAL_CODE_FILE, "r") as f:
                return f.read()
        except FileNotFoundError:
            return 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Crie seu código aqui!")\n}'

    def save_code(self):
        """Salva o conteúdo atual do editor para o arquivo temporário de envio."""
        current_code = self.code_text.get("1.0", tk.END)
        try:
            with open(TEMP_SEND_FILE, "w") as f:
                f.write(current_code)
            messagebox.showinfo(
                "Sucesso", f"Código salvo com sucesso em '{TEMP_SEND_FILE}'."
            )
            return True
        except Exception as e:
            messagebox.showerror("Erro de Arquivo", f"Falha ao salvar o código: {e}")
            return False

    def display_result(self, content, is_error=False):
        """Exibe o resultado na área de texto."""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        tag = "error" if is_error else "output"
        color = "red" if is_error else "green"

        self.result_text.tag_config(tag, foreground=color)
        self.result_text.insert(tk.END, content, tag)
        self.result_text.config(state=tk.DISABLED)

    def send_code(self):
        """Executa o cliente C para enviar o código."""
        if not self.save_code():
            return

        self.display_result("Enviando código para o servidor C executor...")

        try:
            # Executa o cliente C, passando o nome do arquivo temporário como argumento
            # o cliente C lê o arquivo, faz o JSON, envia e recebe a resposta JSON
            result = subprocess.run(
                [CLIENT_EXECUTABLE, TEMP_SEND_FILE],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,  # Timeout para a execução remota
            )

            # O cliente C imprime a resposta JSON na saída padrão (stdout)
            raw_output = result.stdout

            # 1. Extrair a string JSON da saída bruta (pode ter logs do cliente C)
            # Procuramos pela primeira e última chave {} para isolar o JSON
            start = raw_output.find("{")
            end = raw_output.rfind("}")

            if start == -1 or end == -1:
                self.display_result(
                    f"ERRO: Cliente C não retornou JSON válido.\nOutput do Cliente:\n{raw_output}",
                    True,
                )
                return

            json_response = raw_output[start : end + 1]

            # 2. Processar o JSON (Converter escapes de volta)
            response = json.loads(json_response)

            # Substitui os escapes do JSON por quebras de linha reais para melhor visualização
            output = response.get("output", "").replace("\\n", "\n").replace('\\"', '"')
            error_msg = (
                response.get("error", "").replace("\\n", "\n").replace('\\"', '"')
            )

            # 3. Exibir o resultado final
            if error_msg:
                self.display_result(error_msg, is_error=True)
            else:
                self.display_result(output)

        except subprocess.CalledProcessError as e:
            # Erro na execução do cliente C (ex: falha ao conectar)
            self.display_result(
                f"ERRO DE EXECUÇÃO DO CLIENTE C:\nCódigo de Retorno: {e.returncode}\nSaída de Erro:\n{e.stderr}",
                True,
            )
        except FileNotFoundError:
            self.display_result(
                f"ERRO: O executável do cliente C não foi encontrado em '{CLIENT_EXECUTABLE}'.",
                True,
            )
        except json.JSONDecodeError:
            self.display_result(
                f"ERRO: O servidor retornou uma string JSON inválida.\nResposta:\n{json_response}",
                True,
            )
        except Exception as e:
            self.display_result(f"Erro inesperado: {e}", True)


# --- Inicialização da Aplicação ---
if __name__ == "__main__":
    # Certifique-se de que o arquivo Go inicial exista para evitar erro ao carregar
    if not os.path.exists(INITIAL_CODE_FILE):
        print(f"ATENÇÃO: Criando o arquivo inicial '{INITIAL_CODE_FILE}'.")
        with open(INITIAL_CODE_FILE, "w") as f:
            f.write(
                'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Hello do GUI!")\n}'
            )

    root = tk.Tk()
    app = RemoteExecutorApp(root)
    root.mainloop()
