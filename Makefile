# moulin-beat — flash du micro:bit v2 monte sur micro:Maqueen V4.2
#
# Le projet tient en plusieurs modules, donc on ne peut pas se contenter de
# `uflash src/main.py` : uflash n'embarque qu'un seul script dans le firmware.
# On flashe le runtime MicroPython nu, puis on depose les modules dans le
# systeme de fichiers du micro:bit avec microfs. MicroPython execute
# automatiquement le main.py qu'il y trouve au demarrage.
#
#   make deps     installe uflash et microfs (dans un venv)
#   make flash    runtime + modules, la totale
#   make sync     modules seulement, sans reflasher le runtime (bien plus rapide)
#   make ls       liste les fichiers presents sur le micro:bit
#   make console  ouvre le REPL serie pour lire les erreurs
#   make check    verifie que le micro:bit est visible et accessible
#   make test     joue les choregraphies sur PC, sans robot

VENV    := .venv
PY      := $(VENV)/bin/python
UFLASH  := $(VENV)/bin/uflash
UFS     := $(VENV)/bin/ufs
MODULES := src/maqueen.py src/beat.py src/choregraphie.py
MAIN    := src/main.py
PORT    := /dev/ttyACM0

.PHONY: help deps flash sync ls console check test clean

help:
	@sed -n 's/^# \{0,1\}//p' $(MAKEFILE_LIST) | sed -n '1,17p'

$(VENV):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip uflash microfs

deps: $(VENV)
	@echo "uflash et microfs installes dans $(VENV)"

flash: deps
	@echo ">>> Runtime MicroPython (efface le systeme de fichiers)"
	$(UFLASH)
	@echo ">>> Attente du remontage du volume MICROBIT"
	@sleep 4
	$(MAKE) sync

sync: deps
	@echo ">>> Copie des modules"
	$(UFS) put $(word 1,$(MODULES))
	$(UFS) put $(word 2,$(MODULES))
	$(UFS) put $(word 3,$(MODULES))
	@echo ">>> Copie du programme principal"
	$(UFS) put $(MAIN)
	@echo
	@echo "Fait. Le robot demarre EN PAUSE : bouton B pour lancer les pales."

ls: deps
	$(UFS) ls

console:
	@echo "REPL sur $(PORT), Ctrl-A puis K pour quitter screen."
	@command -v screen >/dev/null || { echo "screen absent : dnf install screen"; exit 1; }
	screen $(PORT) 115200

check:
	@echo "=== micro:bit ==="
	@lsusb | grep -q "0d28:0204" && lsusb | grep "0d28:0204" \
		|| { echo "ECHEC  micro:bit non detecte"; exit 1; }
	@echo
	@echo "=== Permissions usbfs ==="
	@for d in $$(lsusb | grep "0d28:0204" | sed -E 's|Bus ([0-9]+) Device ([0-9]+).*|\1/\2|'); do \
		stat -c '%n  %A' /dev/bus/usb/$$d; \
	done
	@echo
	@echo "=== Volume MICROBIT ==="
	@ls -d /run/media/$$USER/MICROBIT /media/$$USER/MICROBIT 2>/dev/null \
		|| echo "non monte (uflash en a besoin)"
	@echo
	@echo "=== Port serie ==="
	@ls -l $(PORT) 2>/dev/null || echo "$(PORT) absent"

test:
	python3 tests/test_choregraphie.py

clean:
	rm -rf $(VENV)
