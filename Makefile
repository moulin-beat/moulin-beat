# moulin-beat — flash du micro:bit v2 monte sur micro:Maqueen V4.2
#
# Deux voies mènent au robot, et elles ne valent pas la meme chose.
#
# `make flash` fusionne les modules en un script unique et le confie a uflash,
# qui ecrit par le volume USB de masse. Cette voie ne touche jamais au port
# serie, donc elle marche meme REPL bloque : c'est la voie par defaut.
#
# `make modules` depose les modules separement avec microfs. Plus propre pour
# bidouiller au REPL ensuite, mais entierement suspendu au port serie, lequel se
# bloque des que le programme tourne ou qu'un autre outil tient le port.
#
#   make deps     installe uflash et microfs (dans un venv)
#   make flash    fichier unique par le volume USB — la voie fiable
#   make modules  modules separes par le REPL serie — plus propre, plus fragile
#   make build    fusionne les modules sans rien flasher
#   make sync     recopie les modules sans reflasher le runtime
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

.PHONY: help deps build flash modules sync ls console check test clean

help:
	@sed -n 's/^# \{0,1\}//p' $(MAKEFILE_LIST) | sed -n '1,21p'

$(VENV):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip uflash microfs

deps: $(VENV)
	@echo "uflash et microfs installes dans $(VENV)"

build:
	python3 outils/build_mono.py

# Voie principale. uflash passe par le volume USB de masse et ne touche jamais
# au port serie : c'est ce qui la rend fiable meme quand le REPL est bloque —
# programme occupe, port pris, DAPLink capricieux. Comme uflash n'embarque
# qu'un seul script, on fusionne d'abord les modules.
flash: deps build
	$(UFLASH) build/moulin_beat.py
	@echo
	@echo "Fait. Le robot demarre EN PAUSE : bouton B pour lancer les pales."
	@echo "En pause, le bouton A lance le test des roues."

# Voie alternative : les modules restent separes sur la carte, ce qui est plus
# propre pour bidouiller au REPL, mais depend entierement du port serie.
modules: deps
	@echo ">>> Runtime MicroPython (efface le systeme de fichiers)"
	$(UFLASH)
	@echo ">>> Attente du remontage du volume MICROBIT"
	@sleep 5
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
	@vol=$$(ls -d /run/media/$$USER/MICROBIT /media/$$USER/MICROBIT 2>/dev/null | head -1); \
	if [ -n "$$vol" ]; then \
		echo "monte sur $$vol"; \
		test -f $$vol/DETAILS.TXT && grep -q WebUSB $$vol/DETAILS.TXT \
			&& echo "firmware DAPLink avec WebUSB"; \
	else \
		echo "non monte (uflash en a besoin)"; \
	fi
	@echo
	@echo "=== Port serie ==="
	@ls -l $(PORT) 2>/dev/null || echo "$(PORT) absent"

test:
	python3 tests/test_choregraphie.py

clean:
	rm -rf $(VENV)
