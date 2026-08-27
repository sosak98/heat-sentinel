# Message Slack — #help-technical (FortyGuard Hackathon)

> **Quand envoyer :** maintenant (ou plus tard, c'est au choix). Le bug est
> apparemment résolu, mais l'incident mérite d'être signalé — et ça montre
> au jury que tu interagis activement avec l'API.

---

**Option A — courte (recommandée) :**

> Hi FortyGuard team 👋 We're ClimVision (HeatSentinel). Two quick notes on the
> API from today:
> 1. Around 17:00 UTC the heatmap endpoint started returning `n_cells: 0` for
>    Phoenix AOIs that had returned tiles minutes before (schema had also
>    changed: `date_time` is now an object with `start_date` + `filter_type`).
>    It seems to be back now — we successfully pulled a 2026-08-25 Phoenix
>    day. Just flagging in case it was a rollout issue.
> 2. Coverage question: Cotonou, Benin (6.36, 2.42) returns 0 tiles for a
>    full-day window. Is there a roadmap for West Africa coverage, or a
>    recommended fallback for non-covered cities?
>
> Thanks — our harvest is running smoothly on Phoenix now. 🌵

**Option B — encore plus courte :**

> Hi! Flagging that around 17:00 UTC the heatmap API briefly returned 0 cells
> for Phoenix AOIs (and the `date_time` schema changed to an object) — it's
> back now. Also: is there a roadmap for Cotonou, Benin (6.36, 2.42) coverage?
> We get 0 tiles for full-day windows. ClimVision / HeatSentinel.

---

## À vérifier de ton côté (aujourd'hui / demain)

1. **Solde de crédits** : dashboard FortyGuard → combien de crédits trial te
   restent ? (la récolte 3 jours en cours ≈ 55 requêtes ; si tu as de la
   marge on étend à 7 jours = ~85 requêtes de plus, sinon 3 jours suffisent
   pour la démo)
2. **Session mentor NVIDIA demain 14h00 (Bénin)** — y es-tu allé·e ? Question
   prête si non : *« For a 2 MB model doing 6 h nowcasts on a Jetson, do you
   recommend ONNX Runtime or TensorRT for the edge path, and is there a CUDA-X
   component you'd suggest for vectorized feature processing? »*
3. **Formulaire d'équipe** (team registration form) — envoyé ? → il débloque
   le canal privé.
