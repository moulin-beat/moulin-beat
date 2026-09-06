"""Depose le programme sur le micro:bit, et VERIFIE que la carte l'a accepte.

Pourquoi ce script plutot qu'un appel direct a `uflash` :

1. `uflash` ecrit le fichier et rend la main. Il ne sait rien de ce que DAPLink
   en fait ensuite. Un transfert interrompu laisse un `FAIL.TXT` sur le volume
   et la carte affiche un visage triste suivi d'un code 5xx — mais le `make`
   annoncait quand meme « Fait », et l'on cherchait le bug dans le code pendant
   que la carte tournait sur l'ancien programme. C'est un piege couteux.

2. Le hex fusionne fait pres de deux megaoctets. Ecrit par le canal ordinaire,
   il part dans le cache du noyau et se vide paresseusement vers la carte ; si
   le processus rend la main avant la fin, DAPLink voit un transfert qui traine
   et finit par declarer « The transfer timed out ». On force donc l'ecriture
   jusqu'au materiel avec fsync() avant de rendre la main.

3. La panne est marquee « transient » par DAPLink elle meme : elle se rattrape
   en recommencant. Ce script recommence, au lieu de laisser l'humain le faire.

Le verdict de DAPLink met un instant a apparaitre : le volume se demonte, la
carte se programme, puis le volume revient — et c'est SEULEMENT la qu'un
FAIL.TXT eventuel est lisible. Verifier trop tot rend un faux succes, ce qui est
pire que pas de verification du tout.
"""

import os
import sys
import time

import uflash

ESSAIS = 3

# Temps d'attente du remontage du volume apres programmation.
ATTENTE_VOLUME_S = 30

# Apres le remontage, DAPLink peut encore deposer son FAIL.TXT. On lui laisse
# ce delai avant de conclure au succes.
REPOS_S = 3


def volume():
    """Chemin du volume MICROBIT monte, ou None."""
    utilisateur = os.environ.get("USER", "")
    for base in ("/run/media/%s/MICROBIT" % utilisateur,
                 "/media/%s/MICROBIT" % utilisateur,
                 "/media/MICROBIT"):
        if os.path.isfile(os.path.join(base, "DETAILS.TXT")):
            return base
    return None


def attend_volume(limite=ATTENTE_VOLUME_S):
    """Attend le retour du volume apres programmation. Rend le chemin, ou None."""
    fin = time.time() + limite
    while time.time() < fin:
        chemin = volume()
        if chemin:
            return chemin
        time.sleep(1)
    return None


def depose(script, cible):
    """Ecrit le hex sur la carte, en for(c)ant la sortie du cache.

    C'est le point qui compte : sans fsync, l'ecriture rend la main alors que
    les donnees sont encore dans le cache du noyau, et DAPLink attend.
    """
    with open(script, "rb") as f:
        code = f.read()
    hexa = uflash.embed_fs_uhex(uflash._RUNTIME, code)
    chemin = os.path.join(cible, "micropython.hex")
    with open(chemin, "wb") as f:
        f.write(hexa.encode("ascii"))
        f.flush()
        os.fsync(f.fileno())


def echec_declare(cible):
    """Contenu de FAIL.TXT si DAPLink a refuse, sinon None."""
    chemin = os.path.join(cible, "FAIL.TXT")
    if not os.path.isfile(chemin):
        return None
    with open(chemin) as f:
        return f.read().strip()


def repond_au_repl(port="/dev/ttyACM0"):
    """Le micro:bit parle t il ? Preuve la plus forte que le programme tourne.

    Consultatif : un port pris par un autre outil n'est pas un echec de flash,
    donc on ne fait que le signaler.
    """
    try:
        import serial
    except ImportError:
        return None
    try:
        lien = serial.Serial(port, 115200, timeout=1)
    except Exception:
        return None
    try:
        lien.write(b"\x03")          # interrompt le programme, rend le REPL
        time.sleep(0.5)
        lien.read(4000)
        lien.write(b"\r\nprint('VIVANT')\r\n")
        time.sleep(1)
        vu = b"VIVANT" in lien.read(4000)
        lien.write(b"\x04")          # relance le programme
        return vu
    finally:
        lien.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: flash.py <script.py>")
    script = sys.argv[1]

    for essai in range(1, ESSAIS + 1):
        cible = volume()
        if not cible:
            raise SystemExit(
                "    volume MICROBIT non monte. Verifier le cable, et que le\n"
                "    micro:bit n'est pas en mode bootloader.")

        try:
            os.remove(os.path.join(cible, "FAIL.TXT"))
        except OSError:
            pass

        print("    essai %d/%d : ecriture sur %s" % (essai, ESSAIS, cible))
        depose(script, cible)

        cible = attend_volume()
        if not cible:
            print("    le volume n'est pas revenu apres %d s" % ATTENTE_VOLUME_S)
            continue
        time.sleep(REPOS_S)

        raison = echec_declare(cible)
        if raison is None:
            print("    DAPLink a accepte le programme")
            vivant = repond_au_repl()
            if vivant is True:
                print("    le micro:bit repond : le programme tourne")
            elif vivant is False:
                print("    (le micro:bit ne repond pas au REPL - a verifier)")
            return

        print("    REFUSE par DAPLink :")
        for ligne in raison.splitlines():
            print("      " + ligne)
        if essai < ESSAIS:
            print("    panne declaree transitoire, on recommence")
            time.sleep(2)

    raise SystemExit(
        "\n    Echec apres %d essais. Le TRANSFERT echoue, pas le programme.\n"
        "    Pistes, dans l'ordre : changer de cable USB, brancher en direct\n"
        "    plutot que sur un hub, puis `make modules` qui passe par le port\n"
        "    serie et ignore completement le volume de masse." % ESSAIS)


if __name__ == "__main__":
    main()
