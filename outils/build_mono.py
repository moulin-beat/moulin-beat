"""Fusionne les modules du projet en un unique script pour le micro:bit.

Pourquoi : `ufs` depose les modules un a un, mais il lui faut le REPL serie. Ce
canal se bloque regulierement — programme occupe, port pris par un autre outil,
DAPLink capricieux — et il devient alors impossible de mettre a jour le robot.

`uflash`, lui, passe par le volume USB de masse et ignore le port serie. Mais il
n'embarque qu'un seul script. On concatene donc les modules dans un fichier
unique, en fusionnant leurs imports `microbit` et en supprimant les prefixes de
module devenus inutiles puisque tout partage le meme espace de noms.

    python3 outils/build_mono.py    ->  build/moulin_beat.py

uflash plafonne le script embarque a 20151 octets, et ce projet commente
beaucoup. Si le fichier fusionne depasse, on le regenere sans commentaires ni
docstrings — les sources de src/ restent evidemment intactes.
"""

import ast
import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "src")
SORTIE = os.path.join(RACINE, "build", "moulin_beat.py")

# L'ordre compte : chaque module ne doit dependre que de ce qui precede.
MODULES = ("maqueen", "beat", "choregraphie", "main")


def imports_microbit(texte):
    """Recupere les noms importes depuis `microbit`, sur une ou plusieurs lignes."""
    noms = set()
    for bloc in re.findall(r"from microbit import \(([^)]*)\)", texte):
        noms.update(n.strip() for n in bloc.split(",") if n.strip())
    for ligne in re.findall(r"from microbit import ([^(\n]+)", texte):
        noms.update(n.strip() for n in ligne.split(",") if n.strip())
    return noms


def nettoie(texte):
    """Retire les imports, que l'en-tete du fichier fusionne reprend en bloc."""
    texte = re.sub(r"from microbit import \([^)]*\)\n", "", texte)
    texte = re.sub(r"from microbit import [^(\n]+\n", "", texte)
    texte = re.sub(r"^import (%s)\n" % "|".join(MODULES), "", texte, flags=re.M)
    return texte


def deprefixe(texte):
    """`maqueen.arret()` devient `arret()` : un seul espace de noms desormais.

    Les noms des quatre modules ne se recouvrent pas, la fusion est donc sure.
    Le script verifie cette absence de collision avant d'ecrire quoi que ce soit.
    """
    for module in MODULES:
        texte = re.sub(r"\b%s\.(\w)" % module, r"\1", texte)
    return texte


def noms_definis(texte):
    return set(re.findall(r"^(?:def|class)\s+(\w+)", texte, flags=re.M)) | \
           set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", texte, flags=re.M))


# Limite imposee par uflash au script embarque dans le firmware.
TAILLE_MAX = 20151


def allege(texte):
    """Retire commentaires et docstrings, en repassant par l'arbre syntaxique.

    Passer par `ast` plutot que par des expressions regulieres garantit que le
    resultat reste du Python valide et equivalent : les commentaires se perdent
    a l'analyse, et on retire explicitement les docstrings.
    """
    arbre = ast.parse(texte)

    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.Module, ast.ClassDef,
                                  ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corps = noeud.body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            # Une fonction reduite a sa seule docstring a besoin d'un corps.
            corps[0] = ast.Pass() if len(corps) == 1 else None
            noeud.body = [n for n in corps if n is not None]

    # Une fois les modules concatenes, un seul docstring reste a sa place : les
    # trois autres se retrouvent au milieu du fichier, litteraux inertes que la
    # passe ci dessus ne voit pas puisqu'ils ne sont plus en tete de corps. Ils
    # pesaient 4 ko sur les 20 que uflash accepte.
    arbre.body = [n for n in arbre.body
                  if not (isinstance(n, ast.Expr)
                          and isinstance(n.value, ast.Constant)
                          and isinstance(n.value.value, str))]

    return ast.unparse(arbre)


def construis():
    sources = {}
    for module in MODULES:
        with open(os.path.join(SOURCE, module + ".py")) as f:
            sources[module] = f.read()

    # Garde-fou : deux modules qui definiraient le meme nom se marcheraient
    # dessus en silence une fois fusionnes, et le bug serait indechiffrable.
    vus = {}
    for module in MODULES:
        for nom in noms_definis(sources[module]):
            if nom in vus:
                raise SystemExit(
                    "collision de nom : %s defini dans %s et %s"
                    % (nom, vus[nom], module))
            vus[nom] = module

    noms = set()
    for texte in sources.values():
        noms |= imports_microbit(texte)

    morceaux = [
        '"""moulin-beat, tous modules fusionnes.\n\n'
        "Fichier GENERE par outils/build_mono.py — ne pas editer a la main.\n"
        "Les sources sont dans src/.\n"
        '"""\n',
        "from microbit import %s\n" % ", ".join(sorted(noms)),
    ]

    for module in MODULES:
        corps = deprefixe(nettoie(sources[module])).strip()
        morceaux.append("\n\n# %s\n# %s\n\n%s\n" % (module, "-" * len(module), corps))

    texte = "\n".join(morceaux)

    if len(texte.encode("utf-8")) > TAILLE_MAX:
        avant = len(texte.encode("utf-8"))
        texte = allege(texte)
        apres = len(texte.encode("utf-8"))
        print("allege : %d -> %d octets (limite uflash %d)"
              % (avant, apres, TAILLE_MAX))
        if apres > TAILLE_MAX:
            raise SystemExit(
                "le script fusionne fait encore %d octets, au dela des %d que "
                "uflash accepte. Passer par `make modules`, qui depose les "
                "modules separement et ne connait pas cette limite."
                % (apres, TAILLE_MAX))

    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w") as f:
        f.write(texte)

    print("%s ecrit (%d octets)" % (SORTIE, os.path.getsize(SORTIE)))
    return SORTIE


if __name__ == "__main__":
    construis()
