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

## Lire les erreurs du robot

Quand le programme plante, la trace part sur le port série :

```bash
make console
```

Le micro:bit affiche aussi l'erreur en défilant sur sa matrice, mais le REPL
donne le numéro de ligne.
