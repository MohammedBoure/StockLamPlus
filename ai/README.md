# Module IA (Intelligence Artificielle & Prédictions)

Ce module fournit des outils d'intelligence artificielle et d'analyse prédictive pour la gestion optimisée des stocks et la réduction du gaspillage.

## Contenu du répertoire

- **`__init__.py`** : Point d'entrée du package IA, exportant les services principaux.
- **`ai_service.py`** : Service central orchestrant les prévisions de demande, l'analyse des risques de péremption et la détection d'anomalies de rebuts.
- **`forecasting/demand_forecaster.py`** : Moteur prédictif d'estimation de la consommation future basé sur l'historique des sorties.
- **`risk/expiry_risk_analyzer.py`** : Analyseur de risque de péremption identifiant les lots critiques avant expiration selon la cadence d'utilisation.
- **`anomaly/waste_detector.py`** : Détecteur d'anomalies identifiant les pertes ou rebuts anormaux.
