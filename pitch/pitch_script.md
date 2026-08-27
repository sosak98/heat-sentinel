# Script de pitch — HeatSentinel (3 minutes, FR)

> Consecrations : ~420 mots ≈ 3 min à débit normal. Lancer le dashboard
> AVANT de parler. Les chiffres en gras = à regarder dans le dashboard.

---

**[0:00 — Accroche]**
« La chaleur est le danger climatique le plus mortel au monde : deux millions
de morts prématurées par an. Et à Cotonou — ma ville, environ sept cent mille
habitants dans la commune, un million et demi avec l'agglomération — la
chaleur est **humide** : avec l'humidité, le **ressenti dépasse quarante
degrés**, et il n'existe **aucun système d'alerte précoce hyperlocal**. Les
bulletins météo parlent de l'aéroport, qui est à dix kilomètres des rues. Et
quand ils arrivent à huit heures, le pic, lui, est à quinze heures. »

**[0:45 — Le basculement]**
« C'est là que FortyGuard change la partie. Leur Temperature API mesure la
chaleur **à deux mètres du sol, avec une résolution de vingt mètres carrés** —
au niveau de la rue, du marché, de la cour d'école. La donnée existe
enfin au bon endroit. Ce qui manquait, c'était le cerveau : le système qui
regarde, qui prédit, qui décide, qui agit. C'est exactement ce qu'on a construit. »

**[1:20 — La solution, montrer le dashboard]**
« HeatSentinel est une **IA agentique**. Regardez l'écran : **vingt points de
mesure de la Temperature API de FortyGuard** — à vingt mètres carrés près, à
deux mètres du sol. Cotonou est notre cible de déploiement ; la mesh ne la
couvre pas encore, nous l'avons vérifié, donc **la démo tourne sur Phoenix,
avec les vraies données** — vous voyez en bas le panneau « données réelles » :
ces minimum, moyenne et maximum proviennent directement du maillage FortyGuard.
Le modèle — un **deux méga-octets** — fait un **nowcast du pic de chaleur six
heures à l'avance, par point de mesure, avec une erreur moyenne de zéro
virgule vingt-six degré sur Cotonou, zéro virgule soixante-et-un sur Phoenix,
R carré de zéro virgule neuf-cinq et mieux**. Et le flux simulé lui-même est
**recalé jour par jour sur ces mesures réelles**. Un détecteur simple, un
z-score sur quarante-huit heures, repère les anomalies : un micro-pic local,
un capteur qui dérives. Et l'agent, en haut à droite, prend la décision : pas
de black box, pas de dépendance LLM — un moteur de politique transparent qui
déduplique, qui n'escale que si nécessaire, et qui tient un registre d'audit.
Quand un quartier passe à **critique**, l'alerte part par SMS ou WhatsApp en
français **et en fon** avec les actions concrètes : ouvrir un centre de
rafraîchissement en trente minutes, mettre l'hôpital en vigilance, suspendre
le travail extérieur de quatorze heures à dix-sept heures. »

**[2:15 — L'angle qui nous différencie]**
« Deux choses nous distinguent. **Premièrement, l'edge** : ce modèle de deux
méga-octets tourne sur un **NVIDIA Jetson** en moins de dix millisecondes,
hors-ligne, pendant les coupures de courant. Le kit gagnant du hackathon
devient littéralement notre premier capteur citoyen — un nœud de douze
dollars de capteurs sur un Jetson, calibré contre l'API. **Deuxièmement,
l'échelle** : notre chemin d'entraînement RAPIDS et cuML passe de vingt
nœuds à des millions de cellules, sur GPU. Petit modèle sur l'edge,
entraînement massif sur le cloud : l'architecture edge-cloud que NVIDIA
déploie en production. »

**[2:50 — Clôture]**
« En douze mois, cinq sites protégés à Cotonou : l'hôpital régional, trois
écoles, le marché du port. Alerte en soixante secondes, pas en heures.
Phoenix nous prouve la stack sur données réelles, Cotonou est la cible —
puis Abu Dhabi, la même API, des physiques différents. La chaleur n'attendra
pas. Nous non plus. Merci. »

---

## Questions probables du jury & réponses

**« Vos données sont simulées, non ? »**
« Non — et c'est la meilleure nouvelle du projet. On a branché la clé trial,
on a **testé la couverture** : Cotonou n'est pas encore dans la mesh, Phoenix
oui. On a branché la clé trial et on a **récolté de vraies tuiles FortyGuard
sur Phoenix : trois jours complets, vingt points, soixante lectures** (24→26
août — Downtown a culminé à 42,91 °C le 26) — vous voyez le panneau « données
réelles » du dashboard. Le flux horaire entre les jours réels est simulé —
mais **recalé jour par jour sur les min/moy/max réels**, et le simulateur
Cotonou est calibré sur Open-Meteo (bias −0,6 °C/h, `validate.py`). La
récolte est en cache, elle reprend à l'identique : chaque nouveau jour réel
reçu ré-ancore le modèle. »

**« Pourquoi un nowcast à 6 h plutôt qu'une prévision à 24 h ? »**
« C'est l'horizon d'action. Une alerte à 24 h ne change rien ; à 6 h, un
service d'urgence peut ouvrir un centre de rafraîchissement, un employeur peut
décaler le travail extérieur. Nous optimisons l'impact, pas la portée. »

**« Où est le ML "impressif" ? »**
« Le ML impressionnant est la contrainte : 2 Mo, inférence 10 ms sur un
Jetson, features interprétables, évaluation sans leakage temporel. Et le
différenciateur n'est pas le modèle seul — c'est la boucle complète
donnée → décision → action, avec un registre d'audit. C'est là que la
valeur opérationnelle se crée. »

**« Et le LLM ? Où est l'agentique ? »**
« Notre agent est déterministe et auditable par design — c'est un choix de
sécurité : dans une boucle qui protège des vies, on ne met pas un modèle
stochastique en charge de la décision. Un LLM peut être branché en option
pour rédiger les rapports journaliers ; la boucle de sécurité, elle, reste
transparente. »
