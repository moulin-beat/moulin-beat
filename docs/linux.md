# Flasher depuis Linux

## Le micro:bit n'est pas accessible : "WebUSB error"

Sous Linux, le nœud USB brut du micro:bit appartient à `root:root` en
`crw-rw-r--`. L'utilisateur n'a donc que la lecture, alors que WebUSB — et les
outils de flash — ont besoin de l'écriture.

Symptôme côté [microbit.org](https://microbit.org) : une erreur WebUSB qui
demande en boucle de débrancher puis rebrancher le câble. Le message est
générique et ne mentionne jamais les permissions, donc on peut rebrancher
indéfiniment sans rien changer.

Vérifier :

```bash
make check
```

Si la ligne `/dev/bus/usb/...` affiche `crw-rw-r--`, il manque une règle udev.

## La règle udev

```bash
sudo tee /etc/udev/rules.d/99-microbit.rules >/dev/null <<'RULES'
SUBSYSTEM=="usb", ATTR{idVendor}=="0d28", ATTR{idProduct}=="0204", MODE:="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0d28", ATTRS{idProduct}=="0204", MODE:="0666"
ATTRS{idVendor}=="0d28", ATTRS{idProduct}=="0204", ENV{ID_MM_DEVICE_IGNORE}="1"
RULES
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Puis **débrancher et rebrancher le câble** : udev n'applique pas une nouvelle
règle à un périphérique déjà énuméré. `make check` doit alors afficher
`crw-rw-rw-`.

La troisième ligne écarte le micro:bit de ModemManager, actif par défaut sur
Fedora et Ubuntu, qui vient sonder les ports `ttyACM` et perturbe le REPL.

## Points d'attention

- **Le navigateur** : Chrome, Chromium ou Edge. Firefox n'implémente pas WebUSB
  et ne le fera pas. Après un changement de permissions, fermer complètement
  Chrome — les autorisations USB sont mises en cache par onglet.
- **Chromium en Flatpak** : vérifier qu'il a bien `devices=all`, sinon son bac
  à sable bloque l'accès USB.
  ```bash
  flatpak info --show-permissions org.chromium.Chromium | grep devices
  ```
- **Le câble** : beaucoup de câbles micro-USB ne transportent que le courant. Si
  le volume `MICROBIT` ne se monte pas, essayer un autre câble avant tout le
  reste.
- **Firmware DAPLink** : `DETAILS.TXT` sur le volume monté doit lister `WebUSB`
  dans `USB Interfaces`. Sinon, mettre à jour depuis
  [microbit.org/get-started/user-guide/firmware](https://microbit.org/get-started/user-guide/firmware/).

## Le robot ne fait rien après le flash

Trois causes, dans l'ordre de fréquence.

**Le programme est en pause.** C'est le comportement normal au démarrage. La
matrice affiche un petit carré : appuyer sur **B** pour lancer les pales.

**Le micro:bit est vierge.** `make flash` n'a pas été lancé, ou a échoué au
remontage du volume. Vérifier :

```bash
make ls        # doit lister beat.py choregraphie.py main.py maqueen.py
```

Une liste vide signifie que seul le runtime MicroPython est présent :
relancer `make sync`.

**Le Maqueen ne répond pas sur l'I2C.** La matrice fait alors défiler
`Maqueen muet`. Vérifier l'interrupteur du châssis, les piles, et que le
micro:bit est enfiché à fond dans le connecteur.

Pour lever le doute, scanner le bus depuis le REPL (`make console`) :

```python
from microbit import i2c
[hex(a) for a in i2c.scan()]
```

`['0x10']` attendu. Si la liste est vide, c'est bien l'alimentation ou le
connecteur. Si une autre adresse apparaît, la carte n'est pas un Maqueen
standard — un Maqueen **Plus** utilise un autre protocole moteur.

## Le piège du premier échange I2C

Le contrôleur moteur du Maqueen **n'acquitte pas la toute première écriture
I2C** qui suit sa mise sous tension. Elle échoue en `OSError: [Errno 19]
ENODEV`, et elle seule : toutes les suivantes passent.

```
>>> i2c.write(0x10, bytearray([0,0,0]))
OSError: [Errno 19] ENODEV        <- premier échange
>>> i2c.write(0x10, bytearray([0,0,80]))
>>>                                <- passe sans broncher
```

Un code naïf meurt donc sur sa première trame, avant d'avoir rien fait, en
donnant l'impression d'un robot inerte ou d'un micro qui n'entend rien.

`maqueen.roue()` réessaie pour cette raison, et `maqueen.reveille()` absorbe
l'échange initial au démarrage. Ne pas supprimer ces garde-fous en croyant
simplifier le driver.

## ASSERT.TXT : le firmware d'interface a planté

Si un fichier `ASSERT.TXT` apparaît sur le volume `MICROBIT`, ce n'est pas le
programme MicroPython qui a échoué : c'est **DAPLink**, la puce d'interface USB
du micro:bit, distincte du processeur qui exécute le code.

```
Assert
File: ../../../source/daplink/circ_buf.c
Line: 169
Source: Application
```

`circ_buf.c` est le buffer circulaire du canal série. Quand DAPLink s'y met en
défaut, les symptômes sont déroutants parce qu'ils imitent une panne de
programme :

- le port série devient totalement muet, et le reste après rebranchement ;
- `ufs` échoue avec `Could not enter raw REPL`, donc `make modules` et
  `make console` sont hors service ;
- les flashs par volume USB sont **acceptés en apparence** — le fichier est bien
  copié — sans que le programme soit correctement écrit, d'où un micro:bit à
  l'écran noir alors que tout paraît s'être bien passé.

La cause tient au firmware lui-même. Vérifier dans `DETAILS.TXT` :

```bash
grep -E "Build ID|Interface Version|HIC ID" /run/media/$USER/MICROBIT/DETAILS.TXT
```

Un `Build ID` contenant `alpha` signale un firmware de préproduction, connu pour
ce genre d'instabilité. La version stable est **0257** pour les cartes V2.20 et
V2.21, **0255** pour les V2.00.

Le `HIC ID` dit quelle carte on a : `6e052820` correspond au nRF52820, donc une
V2.20/2.21, donc le 0257.

## Mettre à jour le firmware DAPLink

1. Débrancher l'USB **et** couper l'alimentation du châssis. Retirer le
   micro:bit du Maqueen rend la manipulation plus sûre.
2. Télécharger le firmware correspondant à la carte :
   ```bash
   curl -sSLO https://tech.microbit.org/docs/software/assets/DAPLink-factory-release/0257_nrf52820_microbit_if_crc_c782a5ba90_gcc.hex
   ```
3. **Maintenir le bouton RESET** au dos du micro:bit, et brancher l'USB sans le
   relâcher. Un volume **MAINTENANCE** apparaît à la place de `MICROBIT`.
4. Copier le `.hex` sur ce volume, puis attendre que la LED jaune du dos cesse
   de clignoter.
5. Débrancher, rebrancher, et vérifier :
   ```bash
   grep "Interface Version" /run/media/$USER/MICROBIT/DETAILS.TXT
   ```

Le fichier `ASSERT.TXT` disparaît une fois le défaut effacé.

## Lire les erreurs du robot

Quand le programme plante, la trace part sur le port série :

```bash
make console
```

Le micro:bit affiche aussi l'erreur en défilant sur sa matrice, mais le REPL
donne le numéro de ligne.
