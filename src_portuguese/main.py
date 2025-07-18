import os
from crew import Juriscrew

def run():
    caminho = input("Digite o caminho do arquivo PDF :\n> ")
    caminho_absoluto = os.path.abspath(caminho)
    if not os.path.exists(caminho_absoluto):
        print(f"Erro: O caminho '{caminho_absoluto}' não existe.")
        return

    print("🔍 Iniciando análise jurídica do documento...")
    inputs = {
        'info': caminho_absoluto
    }
    result = Juriscrew().crew().kickoff(inputs=inputs)
    print("✅ Fluxo concluído!")
    print("Resultado:", result)
    

if __name__ == "__main__":
    run()