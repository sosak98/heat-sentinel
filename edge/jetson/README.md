# Edge Network — NVIDIA Jetson

> **Vision post-hackathon** — le Dockerfile « Jetson-ready » documente le
> déploiement edge ; **non testé sur matériel réel**. Le kit gagnant du
> hackathon serait le premier nœud du maillage.

HeatSentinel est conçu **edge-first** : le modèle complet (~2 Mo) tourne sur un
NVIDIA Jetson (Nano/Orin) sans cloud.

## Pourquoi un edge network ?

1. **La donnée la plus utile est à 2 m du sol.** Les nœuds FortyGuard mesurent
   au niveau de la rue ; un maillage de capteurs citoyens Jetson complète la
   couverture (marchés, cours d'école, chantiers).
2. **Résilience** : le dashboard, le modèle et l'agent fonctionnent **hors-ligne**
   (pas de dépendance cloud — critique lors des coupures réseau/électriques).
3. **Souveraineté des données** : la ville possède ses données thermiques.

## Matériel d'un nœud (budget ~120 $)

| Composant | Rôle |
|---|---|
| NVIDIA Jetson (Orin Nano / Nano) | Inférence ONNX + agent local |
| Capteur DS18B20 / SHT31 (±0.2 °C) | Température à 2 m du sol |
| Capteur d'humidité + anémomètre USB | Humidité, vent (features du modèle) |
| Solenoïde / écran e-ink optionnel | Action locale (ombrage, affichage) |

## Déploiement

```bash
# 1. Export ONNX du modèle LightGBM (sur la machine de dev)
python -m export_onnx        # → artifacts/model.onnx

# 2. Sur le Jetson (JetPack 5.x + ONNX Runtime pre-installé)
scp artifacts/model.onnx jetson:~/heat-sentinel/
python jetson_inference.py --node CTO-21 --location "Marché Dantokpa"
```

Le nœud :
- lit le capteur local chaque minute,
- enrichit avec le flux FortyGuard (API) quand il est disponible,
- calcule le score de risque en < 10 ms (ONNX Runtime, CPU du Jetson),
- pousse ses alertes au dashboard central **ou agit en local** (mode autonome).

## Lien avec le hackathon

Le kit **NVIDIA Jetson AI Developer Kit** offert aux équipes gagnantes devient
directement le **premier nœud du maillage** : le prix finance la suite du prototype.
