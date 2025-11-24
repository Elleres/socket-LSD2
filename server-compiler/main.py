import json
import os
import subprocess
import sys
import time

# --- Configurações ---
# Nome do arquivo de código Go que será editado e enviado
CODE_FILE = "main.go"
# Nome do arquivo temporário que será enviado ao servidor (Cliente C lerá este arquivo)
TEMP_SEND_FILE = "code_to_send.go"
# Caminho para o executável do cliente C
CLIENT_EXECUTABLE = "./client"
# O comando do editor de texto que será usado (pode ser 'nano', 'vim', 'code', 'open -t', etc.)
# Recomendado usar um editor CLI básico como 'nano' ou 'vim' para melhor portabilidade no terminal.
# Se estiver no macOS, 'open -t' tentará abrir no TextEdit. No Linux, 'nano' é comum.
EDITOR_COMMAND = "nano"
# Porta do servidor C
SERVER_PORT = 8400


def load_initial_code(filename: str) -> str:
    """Carrega o código Go inicial, criando o arquivo se não existir."""
    try:
        with open(filename, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Arquivo '{filename}' não encontrado. Criando um modelo...")
        initial_content = 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Hello do CLI!")\n}'
        try:
            with open(filename, "w") as f:
                f.write(initial_content)
            return initial_content
        except Exception as e:
            print(f"Erro ao criar o arquivo: {e}")
            sys.exit(1)


def run_editor(filename: str):
    """Abre o arquivo no editor de texto padrão."""
    try:
        print(
            f"\nAbrindo '{filename}' no editor ({EDITOR_COMMAND})... Salve e feche o editor para continuar."
        )
        # O subprocesso bloqueia até que o editor seja fechado
        subprocess.run([EDITOR_COMMAND, filename], check=True)
        print(f"Código salvo e editor fechado.")
        return True
    except FileNotFoundError:
        print(
            f"ERRO: Comando do editor '{EDITOR_COMMAND}' não encontrado. Tente 'vim' ou 'nano'."
        )
        return False
    except subprocess.CalledProcessError as e:
        print(f"ERRO: O editor retornou um erro: {e}")
        return False


def send_code():
    """Executa o cliente C para enviar o código."""

    # 1. Copia o código principal para o arquivo que o cliente C irá ler
    try:
        current_code = ""
        with open(CODE_FILE, "r") as f_main:
            current_code = f_main.read()

        with open(TEMP_SEND_FILE, "w") as f_temp:
            f_temp.write(current_code)

    except Exception as e:
        print(f"ERRO: Falha ao copiar/salvar o arquivo de envio: {e}")
        return

    print(f"\n--- Enviando código para o servidor C em {SERVER_PORT} ---")

    try:
        # Executa o cliente C, passando o nome do arquivo temporário como argumento
        result = subprocess.run(
            [CLIENT_EXECUTABLE, TEMP_SEND_FILE],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        # O cliente C imprime a resposta JSON na saída padrão (stdout)
        raw_output = result.stdout

        # 2. Processar a string JSON retornada pelo cliente C
        start = raw_output.find("{")
        end = raw_output.rfind("}")

        if start == -1 or end == -1:
            print(
                f"ERRO: Cliente C não retornou JSON válido.\nOutput Bruto:\n{raw_output}"
            )
            return

        json_response = raw_output[start : end + 1]
        response = json.loads(json_response)

        # Substitui os escapes do JSON por quebras de linha reais para melhor visualização
        output = response.get("output", "").replace("\\n", "\n").replace('\\"', '"')
        error_msg = response.get("error", "").replace("\\n", "\n").replace('\\"', '"')

        # 3. Exibir o resultado final
        print("\n" + "=" * 50)
        print("✅ RESULTADO DA EXECUÇÃO REMOTA")
        print("=" * 50)

        if error_msg:
            print("🔴 ERRO DE COMPILAÇÃO/EXECUÇÃO NO SERVIDOR:")
            print("-" * 40)
            print(error_msg)
            print("-" * 40)
        else:
            print("🟢 SAÍDA PADRÃO (STDOUT):")
            print("-" * 40)
            print(output)
            print("-" * 40)

    except subprocess.CalledProcessError as e:
        print(f"ERRO FATAL NO CLIENTE C: Falha na conexão ou execução.\n{e.stderr}")
    except FileNotFoundError:
        print(
            f"ERRO: O executável do cliente C não foi encontrado em '{CLIENT_EXECUTABLE}'."
        )
    except json.JSONDecodeError:
        print(
            f"ERRO: Resposta inválida (JSON corrompido) recebida do servidor/cliente.\nResposta:\n{json_response}"
        )
    except Exception as e:
        print(f"Erro inesperado durante a execução: {e}")


def main_menu():
    """Loop principal da interface CLI."""

    # Garante que o arquivo principal exista antes de começar
    load_initial_code(CODE_FILE)

    while True:
        print("\n" + "=" * 50)
        print(f"⚙️ EXECUTOR REMOTO GO (CLI) | Arquivo: {CODE_FILE}")
        print("=" * 50)
        print("1. [E]ditar Código (Abre o editor)")
        print("2. [S]end/Executar")
        print("3. [V]er Código Atual")
        print("4. [Q]uit/Sair")
        print("-" * 50)

        choice = input("Escolha a opção (1-4): ").strip().lower()

        if choice in ("1", "e", "editar"):
            run_editor(CODE_FILE)

        elif choice in ("2", "s", "send", "executar"):
            send_code()

        elif choice in ("3", "v", "ver"):
            print("\n" + "~" * 20 + f" CÓDIGO ATUAL EM {CODE_FILE} " + "~" * 20)
            try:
                with open(CODE_FILE, "r") as f:
                    print(f.read())
            except:
                print("Não foi possível ler o arquivo.")
            print("~" * (40 + len(CODE_FILE) + 10))

        elif choice in ("4", "q", "quit", "sair"):
            print("Saindo do executor. Adeus!")
            break

        else:
            print("Opção inválida. Tente novamente.")


if __name__ == "__main__":
    main_menu()
