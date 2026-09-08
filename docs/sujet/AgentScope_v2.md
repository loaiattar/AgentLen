# AgentScope
**Normalisation et dashboarding**

## La mission

Vous devez développer **AgentScope**, une application web permettant d’explorer des traces d’utilisation d’agents de développement IA.

Le besoin est simple : comprendre ce que font les agents, quels outils ils utilisent, combien de tokens ils consomment et où ils passent leur temps. Votre application devra réunir des données provenant de plusieurs sources et les rendre lisibles dans une interface commune.

Elle devra également intégrer son propre **agent IA d’aide à l’import**. Un utilisateur doit pouvoir ajouter un nouveau jeu de données, comprendre sa structure et l’intégrer sans quitter l’application ni écrire un script spécifique.

**Votre objectif : publier vendredi soir une première version utilisable et open source sur GitHub.** Vous ne livrez pas seulement une démonstration : une personne extérieure au groupe doit pouvoir installer l’outil, l’utiliser et comprendre comment le faire évoluer.

L’utilisation d’IA pour développer le projet est attendue. Vous restez responsables du fonctionnement de l’application, de son architecture et de la justesse des résultats.

## Organisation du sprint

Chaque promotion sera répartie en **quatre groupes**. Chaque groupe développe sa propre version d’AgentScope dans un dépôt commun à ses membres. Le périmètre est volontairement large : répartissez les chantiers et travaillez en parallèle, avec des interfaces convenues et des intégrations régulières.

**GitHub Projects est obligatoire dès le premier jour.** Votre tableau doit présenter le travail prévu, en cours, en revue et terminé. Chaque tâche doit être liée à une issue, avoir un responsable et un résultat attendu vérifiable. Le tableau doit refléter le travail réel, pas être rempli à la fin pour le rendu.

Les modifications passent par des pull requests, reliées aux issues et relues par un autre membre du groupe avant intégration. Chaque membre doit contribuer à la réalisation et aux revues. La participation sera appréciée à travers les tâches, les décisions et les contributions, pas au nombre de lignes ou de commits.

| Étape | Résultat attendu |
|---|---|
| **Jour 1 — Cadrer et démarrer** | Dépôt, GitHub Projects, répartition du travail, première architecture et modèle de données. Faire fonctionner un premier parcours, du fichier importé à un indicateur affiché. |
| **Jour 2 — Construire le socle** | Ingestion fiable, normalisation, contrôles de qualité et premiers dashboards alimentés par les données réelles. |
| **Jour 3 — Ouvrir à d’autres sources** | Agent d’aide à l’import, mapping modifiable, prévisualisation et intégration d’une deuxième source depuis l’interface. Vérifier le fonctionnement avec un deuxième modèle IA. |
| **Jour 4 — Stabiliser et publier** | Tester une structure inconnue, corriger, finaliser la documentation et publier la release vendredi soir. |

N’attendez pas le dernier jour pour intégrer le travail des différents membres ou lancer les tests. Les fonctionnalités complémentaires passent après un parcours principal fiable.

## Les données

Vous commencerez avec **TraceLab**, qui publie des traces réelles de sessions Claude Code et Codex. Utilisez le fichier JSONL publié, et non la base DuckDB ou l’application déjà fournies par le projet. [1]

Pour élargir votre application, vous pourrez utiliser **SWE-chat**, qui rassemble des sessions de développement, des conversations, des appels d’outils et des informations sur les dépôts associés. [2]

**Trace Commons** propose également des sessions conservées dans les formats natifs de différents agents. Il pourra servir à tester l’import d’une structure que votre application ne connaît pas encore. [3]

Travaillez sur des extraits réels de taille raisonnable. Documentez leur provenance, leur version et la façon dont vous les avez sélectionnés. Les données présentées dans les dashboards ne doivent pas être générées artificiellement ; les données fictives restent autorisées pour les tests.

## Ce que doit permettre l’application

### Importer et normaliser

L’utilisateur peut importer un ou plusieurs fichiers, consulter un aperçu et retrouver l’historique des imports. L’application doit prendre en charge **JSONL et au moins un format tabulaire : CSV ou Parquet**.

Concevez un modèle relationnel commun aux différentes sources. Il doit distinguer les sessions, les appels aux modèles et les appels d’outils, avec des clés et des relations explicites. Précisez ce que représente une ligne dans chaque table. Visez la troisième forme normale et justifiez les éventuelles exceptions ; des vues ou tables agrégées peuvent compléter ce modèle pour le dashboard.

Conservez les données d’origine et la provenance des enregistrements. Les valeurs absentes, unités et identifiants doivent être traités explicitement. Réimporter le même fichier ne doit pas doubler les résultats.

Chaque import produit un bilan : éléments importés, doublons, rejets et informations manquantes. Les rejets doivent pouvoir être consultés et expliqués.

### Ajouter une source avec l’aide d’un agent IA

Depuis l’interface, l’utilisateur lance l’analyse d’un fichier inconnu. L’agent peut consulter un échantillon, obtenir un profil des champs et proposer des correspondances avec votre modèle de données.

Il doit pouvoir expliquer ses propositions et signaler les ambiguïtés. L’utilisateur peut échanger avec lui, corriger une correspondance et prévisualiser le résultat avant de valider l’import.

**L’IA propose un mapping ; elle ne modifie pas directement la base.** Ce mapping doit être enregistré, modifiable et réutilisable. Votre moteur d’import applique des transformations contrôlées, sans exécuter librement du code produit par le modèle.

L’objectif est d’intégrer une nouvelle structure par configuration, pas d’ajouter un connecteur codé à la main pour chaque dataset. Vous n’avez pas à reconnaître tous les formats possibles, mais votre application doit expliquer ce qu’elle ne sait pas interpréter.

### Explorer et comprendre

Le dashboard doit proposer **au moins quatre indicateurs, trois visualisations et une vue détaillée d’une session**. Prévoyez des filtres par source, agent ou modèle, et par période lorsque les données le permettent.

À vous de choisir les représentations utiles : activité, consommation de tokens, répartition des outils, durée des sessions, erreurs observées ou utilisation du cache, par exemple.

Chaque indicateur doit avoir une définition accessible : calcul, unité, périmètre et traitement des valeurs manquantes. Une donnée indisponible ne doit pas devenir un zéro. Les métriques non comparables entre sources doivent rester séparées ou être signalées.

Depuis un graphique, l’utilisateur doit pouvoir retrouver les sessions ou enregistrements correspondants. Le dashboard doit aussi rendre visible la qualité des données importées.

## Architecture et maintenabilité

**La Clean Architecture et la maintenabilité sont obligatoires. L’architecture du projet sera davantage regardée que le code lui-même.** Le découpage des responsabilités, le sens des dépendances, la cohérence des interfaces et la capacité à faire évoluer l’outil compteront davantage que la quantité de code produite.

Séparez le domaine métier, les cas d’utilisation, les interfaces utilisateur ou API et l’infrastructure. Le cœur métier ne doit pas dépendre du framework web, de la base de données ou du fournisseur d’IA. Les accès au stockage, au modèle IA et aux fichiers passent par des interfaces explicites et des implémentations remplaçables.

Les règles de normalisation, de validation et de calcul des indicateurs doivent être testables sans lancer l’interface ni appeler un service IA réel. Une modification de l’interface ou un changement de fournisseur IA ne doit pas imposer de réécrire ces règles.

Documentez l’architecture avec un schéma des composants et de leurs dépendances, ainsi que quelques décisions courtes expliquant vos choix et compromis. Des dossiers nommés « domain » ou « infrastructure » ne suffisent pas : la séparation doit être réelle.

**Un monolithe modulaire suffit.** Aucun microservice n’est demandé. Privilégiez une architecture simple, cohérente et comprise par toute l’équipe.

### Un modèle IA interchangeable

**L’IA chargée d’identifier la structure des données et de proposer les mappings ne doit pas dépendre d’un modèle ou d’un fournisseur unique.** Pour les fournisseurs pris en charge, le choix du fournisseur, du modèle et de son point d’accès doit se faire par configuration, sans modifier le code métier ni le moteur d’import. Les identifiants de modèles ne doivent pas être codés en dur.

Prévoyez une interface commune et des adaptateurs isolant les particularités de chaque fournisseur. Ajouter un fournisseur non encore pris en charge doit se limiter à un nouvel adaptateur et à son raccordement, sans réécrire l’application. Les réponses des modèles sont converties vers un même contrat de mapping, puis validées par l’application. Les mappings déjà enregistrés doivent rester utilisables après un changement de modèle.

**Testez et documentez au moins deux configurations utilisant des modèles distincts.** Les modèles peuvent être distants ou locaux. Les propositions ne seront pas nécessairement identiques, mais le parcours d’analyse, de validation et d’import doit fonctionner dans les deux cas. Prévoyez également un substitut de test permettant d’exécuter les tests automatisés sans appel à un service IA réel.

## Contraintes de réalisation

Les technologies sont libres. L’application doit être exécutable à partir du dépôt et les tableaux de bord doivent utiliser les données réellement importées, sans valeurs codées en dur. Une vérification automatisée doit exécuter les tests à chaque pull request.

Les statistiques sont calculées par le programme, pas estimées par l’IA. Ne transmettez au modèle que les profils et échantillons nécessaires, après filtrage des informations sensibles. Les textes présents dans les traces sont des données à analyser, jamais des instructions à exécuter. Aucune clé API ne doit figurer dans le dépôt ou le code livré au navigateur.

Une connexion directe à Hugging Face, l’import par URL, la détection d’anomalies ou un assistant de questions sur les données constituent des prolongements possibles. Ils ne remplacent pas le fonctionnement du parcours principal : **importer, vérifier, normaliser, explorer**.

## Publication et livrables

**Vendredi soir, chaque groupe remet le lien de son dépôt GitHub public, de son GitHub Projects et d’une release identifiée**, par exemple `v0.1.0`. Le dépôt doit contenir :

- **L’application**, les dépendances, les migrations ou scripts SQL, une configuration d’exemple sans secrets et les tests automatisés.
- **Un README de prise en main**, une licence open source explicite, un guide de contribution et des notes de version indiquant les fonctionnalités livrées et les limites connues.
- **La documentation d’architecture et de données** : schéma des composants, diagramme relationnel, principales décisions, définitions des indicateurs et mappings utilisés pour au moins deux sources distinctes. Documentez les modèles IA testés, les fournisseurs pris en charge et la procédure de changement de modèle.
- **Trois observations chiffrées tirées des données**, avec les sources et les filtres permettant de les retrouver. Mentionnez également les outils IA employés et les composants externes réutilisés.

Les tests doivent notamment vérifier qu’un réimport ne crée pas de doublons, que les relations sont conservées, qu’un indicateur reste correct après jointure et filtrage, et qu’un mapping invalide est refusé avec une explication. Joignez un compte rendu de vérification du parcours d’identification et d’import avec les deux modèles IA, sans publier de secrets ni de données sensibles.

Ne publiez ni secrets ni données sensibles. Pour les datasets, fournissez les références, la méthode de récupération et la sélection des extraits ; ne les ajoutez au dépôt que si leurs conditions de redistribution le permettent.

Un hébergement public de l’application n’est pas exigé. En revanche, une personne extérieure doit pouvoir repartir d’un clone du dépôt, suivre le README et reproduire le parcours principal avec ses propres clés API si nécessaire.

## Évaluation

Il n’y aura pas de soutenance. L’évaluation portera sur l’application remise, son architecture, ses tests, sa documentation et les traces du travail d’équipe dans GitHub.

| Critère | Points |
|---|---:|
| Architecture logicielle, Clean Architecture, maintenabilité et interchangeabilité de l’IA | 7 |
| Modèle de données, normalisation et traçabilité | 4 |
| Fonctionnement de l’ingestion et de l’agent IA, dashboard et justesse des indicateurs | 4 |
| Travail d’équipe, suivi GitHub Projects et revues de pull requests | 3 |
| Publication open source, documentation et reproductibilité | 2 |
| **Total** | **20** |

Lors de la correction, un extrait non distribué au départ pourra être importé. Il respectera l’un des formats obligatoires et contiendra des données relevant du périmètre du projet. **L’intégration devra se faire depuis l’interface, sans modification du code.** Les échanges avec l’agent et les corrections du mapping dans l’application sont autorisés. Le changement de modèle par configuration pourra également être vérifié parmi les configurations documentées.

Un import partiel, correctement expliqué, est préférable à un import apparemment réussi qui produit des chiffres faux. Une version limitée mais bien structurée et maintenable sera mieux valorisée qu’une accumulation de fonctionnalités fragiles.

## Sources des jeux de données

[1] TraceLab — SyFI Lab, University of Washington : https://github.com/uw-syfi/TraceLab

[2] SWE-chat — SALT-NLP : https://huggingface.co/datasets/SALT-NLP/SWE-chat

[3] Trace Commons — Agent Traces : https://huggingface.co/datasets/trace-commons/agent-traces

Documentez dans votre rendu les versions et dates de récupération des jeux de données utilisés.
