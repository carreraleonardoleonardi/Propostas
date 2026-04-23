"""
aplicar_patch_caminhos.py — Carrera Signature
Execute UMA VEZ para corrigir os caminhos de saída de todos os scripts.
Salva backup de cada arquivo antes de modificar.

Uso:
    python Dados/aplicar_patch_caminhos.py
"""

import os
import shutil
import re

DADOS_DIR = os.path.dirname(os.path.abspath(__file__))

# Bloco a injetar logo após os imports de cada script
BLOCO_CAMINHO = '''
# ── Caminho padrão para pasta Dados\ ─────────────────────────────────────────
import os as _os
_DADOS_DIR = os.path.dirname(os.path.abspath(__file__))

def _dados_path(nome):
    """Retorna caminho completo dentro de Dados/"""
    return os.path.join(_DADOS_DIR, nome)
# ─────────────────────────────────────────────────────────────────────────────
'''

# Substituições por script: (script, [(old, new), ...])
PATCHES = {
    "Extracao_LM.py": [
        (
            'with pd.ExcelWriter("Lista_LM.xlsx", mode="w", engine="openpyxl") as writer:',
            'with pd.ExcelWriter(_dados_path("Lista_LM.xlsx"), mode="w", engine="openpyxl") as writer:',
        ),
        (
            'with pd.ExcelWriter(\n        "Lista_LM.xlsx",\n        mode="a",',
            'with pd.ExcelWriter(\n        _dados_path("Lista_LM.xlsx"),\n        mode="a",',
        ),
        (
            'with pd.ExcelWriter("Lista_LM.xlsx", mode="a",',
            'with pd.ExcelWriter(_dados_path("Lista_LM.xlsx"), mode="a",',
        ),
        (
            'file_name = "Lista_LM_Concluidos.xlsx"',
            'file_name = _dados_path("Lista_LM_Concluidos.xlsx")',
        ),
    ],
    "Estrutura_Carros.py": [
        (
            'ARQUIVO_EXCEL = "Lista_LM.xlsx"',
            'ARQUIVO_EXCEL = _dados_path("Lista_LM.xlsx")',
        ),
        (
            'final_carros.to_excel("vListaCarrosDetalhes.xlsx", index=False)',
            'final_carros.to_excel(_dados_path("vListaCarrosDetalhes.xlsx"), index=False)',
        ),
        (
            'final_cons.to_excel("vListaConsultoresDetalhes.xlsx", index=False)',
            'final_cons.to_excel(_dados_path("vListaConsultoresDetalhes.xlsx"), index=False)',
        ),
    ],
    "Executa_Precos.py": [
        (
            '.to_excel(f"Ofertas_{str(channel).replace(\' \', \'_\')}.xlsx", index=False)',
            '.to_excel(_dados_path(f"Ofertas_{str(channel).replace(\' \', \'_\')}.xlsx"), index=False)',
        ),
        (
            'df_sd.to_excel("Ofertas_Sign_and_Drive.xlsx", index=False)',
            'df_sd.to_excel(_dados_path("Ofertas_Sign_and_Drive.xlsx"), index=False)',
        ),
        (
            'df_total.to_excel("Ofertas_Todos_SalesChannels.xlsx", index=False)',
            'df_total.to_excel(_dados_path("Ofertas_Todos_SalesChannels.xlsx"), index=False)',
        ),
    ],
    "Extrator_LM_Users.py": [
        (
            'arquivo_entrada = "Lista_Usuarios_LM.xlsx"',
            'arquivo_entrada = _dados_path("Lista_Usuarios_LM.xlsx")',
        ),
        (
            'arquivo_saida = "Usuarios_LM.xlsx"',
            'arquivo_saida = _dados_path("Usuarios_LM.xlsx")',
        ),
    ],
}


def _encontrar_ponto_insercao(codigo):
    """
    Encontra a linha após o último import para injetar o bloco de caminho.
    Retorna o índice da linha onde inserir.
    """
    linhas = codigo.split("\n")
    ultimo_import = 0
    for i, linha in enumerate(linhas):
        stripped = linha.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            ultimo_import = i
    return ultimo_import + 1


def aplicar_patch(nome_script, substituicoes):
    path = os.path.join(DADOS_DIR, nome_script)

    if not os.path.exists(path):
        print(f"  ⚠️  {nome_script} não encontrado — pulando")
        return False

    # Backup
    backup = path + ".backup"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"  💾 Backup criado: {nome_script}.backup")

    with open(path, "r", encoding="utf-8") as f:
        codigo = f.read()

    # Verifica se já foi patchado
    if "_dados_path" in codigo:
        print(f"  ✅ {nome_script} já foi patchado anteriormente")
        return True

    # Injeta bloco de caminho após imports
    linhas = codigo.split("\n")
    pos = _encontrar_ponto_insercao(codigo)
    linhas.insert(pos + 1, BLOCO_CAMINHO)
    codigo = "\n".join(linhas)

    # Aplica substituições
    aplicadas = 0
    for old, new in substituicoes:
        if old in codigo:
            codigo = codigo.replace(old, new)
            aplicadas += 1
        else:
            # Tenta substituição mais flexível (ignora espaços extras)
            old_norm = " ".join(old.split())
            for linha in codigo.split("\n"):
                if old_norm in " ".join(linha.split()):
                    print(f"  ⚠️  Substituição não encontrada exatamente: {old[:60]}...")
                    break

    with open(path, "w", encoding="utf-8") as f:
        f.write(codigo)

    print(f"  ✅ {nome_script} — {aplicadas}/{len(substituicoes)} substituições aplicadas")
    return True


def restaurar_backup(nome_script):
    """Restaura o backup caso algo dê errado."""
    path    = os.path.join(DADOS_DIR, nome_script)
    backup  = path + ".backup"
    if os.path.exists(backup):
        shutil.copy2(backup, path)
        print(f"  ✅ {nome_script} restaurado do backup")
    else:
        print(f"  ⚠️  Backup não encontrado para {nome_script}")


def main():
    print("=" * 55)
    print("  PATCH DE CAMINHOS — CARRERA SIGNATURE")
    print("=" * 55)
    print(f"  Pasta Dados: {DADOS_DIR}")
    print()

    sucesso = 0
    for script, subs in PATCHES.items():
        print(f"📝 {script}")
        ok = aplicar_patch(script, subs)
        if ok:
            sucesso += 1
        print()

    print("=" * 55)
    print(f"✅ {sucesso}/{len(PATCHES)} scripts patchados")
    print()
    print("Agora todos os arquivos Excel serão salvos em:")
    print(f"  {DADOS_DIR}\\")
    print()
    print("Para restaurar o original de algum script:")
    print("  python aplicar_patch_caminhos.py --restaurar NomeScript.py")


if __name__ == "__main__":
    import sys
    if "--restaurar" in sys.argv:
        idx = sys.argv.index("--restaurar")
        if idx + 1 < len(sys.argv):
            restaurar_backup(sys.argv[idx + 1])
    else:
        main()