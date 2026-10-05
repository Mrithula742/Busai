# 🚌 BusSure — AI-Based Public Bus Journey Reliability System

**BusSure** is a research-oriented AI system for predicting **bus travel time, passenger crowd levels, and journey reliability** using spatio-temporal deep-learning techniques.

Instead of providing only scheduled bus timings, BusSure aims to help passengers understand:

- How long the journey may take
- Expected bus arrival/travel time
- How crowded the bus may be
- How reliable the journey is likely to be
- Factors that may contribute to delay or crowding

BusSure is designed as a **general public-transport research framework** and is not restricted to a single city or state.

The current models are developed and evaluated using publicly available transport datasets. Performance in a new city must be experimentally evaluated before claiming the same accuracy.

---

# 1. Research Problem

Public bus journeys are affected by changing traffic conditions, stop-level delays, passenger boarding and alighting, dwell time, time of day, and interactions between connected bus stops.

Traditional timetable-based systems mainly answer:

> **“When is the bus scheduled to arrive?”**

However, passengers also need answers to questions such as:

> **“How long will my actual journey take?”**

> **“Will the bus be crowded?”**

> **“How reliable is this journey?”**

BusSure therefore investigates the following research problem:

> **Can spatio-temporal deep-learning models capture the spatial and temporal behaviour of public bus networks to predict travel time and passenger crowding and use these predictions to provide journey-level reliability information?**

The project focuses on two primary prediction tasks:

1. **Bus travel-time / ETA prediction**
2. **Passenger load / crowd prediction**

The outputs of these models are subsequently used to support journey reliability and passenger decision-making.

---

# 2. Research Objectives

The main objectives of BusSure are:

1. Model a public bus network as a **spatio-temporal system**.
2. Predict bus travel time using historical and network-related information.
3. Predict passenger load/crowding using boarding, alighting and temporal information.
4. Convert predicted passenger load into understandable **Low, Medium and High** crowd levels.
5. Combine travel-time and crowd information to support journey reliability assessment.
6. Evaluate the proposed models using quantitative performance metrics.
7. Compare the proposed approaches with appropriate baseline methods.
8. Evaluate performance on unseen data to study model generalization.
9. Provide a reproducible experimental pipeline.

---

# 3. Research Gap and Proposed Contribution

Previous research has independently investigated several public-transport problems, including:

- Bus arrival-time prediction
- Bus travel-time prediction
- Passenger-demand forecasting
- Passenger occupancy prediction
- Delay propagation
- Public transport network modelling

Graph-based deep-learning approaches have demonstrated that connected bus stops and road segments contain important spatial relationships.

Similarly, temporal deep-learning methods have demonstrated that historical observations are important for understanding changing transport conditions.

Passenger-flow studies have also shown that crowding varies both spatially across the transport network and temporally throughout the day.

However, these problems are frequently investigated independently.

## BusSure's Proposed Contribution

BusSure investigates an integrated framework in which:

**Spatio-temporal travel-time prediction**

and

**Spatio-temporal passenger crowd prediction**

are combined to support:

**Journey-level reliability and passenger decision support.**

The project therefore investigates not only:

> **“When will the bus arrive?”**

but also:

> **“How long may the journey take, how crowded may it be, and how reliable is that journey information?”**

The contribution is evaluated experimentally rather than assuming that the proposed approach automatically outperforms existing methods.

---

# 4. Proposed Methodology

BusSure currently contains two primary AI modelling components.

## 4.1 Travel-Time Prediction — DCRNN

For bus travel-time prediction, BusSure uses a:

### Diffusion Convolutional Recurrent Neural Network (DCRNN)

Bus travel-time prediction contains two important dependencies:

### Spatial Dependency

A bus does not move between independent locations.

Conditions at one stop or road segment can affect subsequent parts of the route.

### Temporal Dependency

Travel conditions also change over time because of:

- traffic,
- peak/off-peak periods,
- operational variation,
- previous bus movement,
- and historical travel patterns.

DCRNN combines:

**Diffusion-based graph convolution**

with

**Recurrent neural-network temporal modelling**

to learn both types of relationships.

### Input

Depending on the available dataset features, model inputs are constructed from:

- Bus/segment observations
- Stop/segment relationships
- Historical travel information
- Temporal information
- Network connectivity
- Operational attributes

### Output

The model predicts travel-time information that can be used for:

- ETA estimation
- Journey-duration estimation
- Delay analysis
- Journey reliability assessment

---

## 4.2 Passenger Crowd Prediction — ST-GCN

For passenger crowd prediction, BusSure uses a:

### Spatio-Temporal Graph Convolutional Network (ST-GCN)

Passenger crowding is also a spatial and temporal problem.

Crowding at a particular location may depend on:

- Passenger boarding
- Passenger alighting
- Previous passenger load
- Time of day
- Stop relationships
- Route progression
- Passenger-flow patterns

ST-GCN is used to learn these spatial and temporal relationships.

### Input

Depending on dataset availability, features include:

- Boarding counts
- Alighting counts
- Passenger load
- Stop information
- Network relationships
- Temporal features

### Output

The model predicts passenger load/crowding.

For passenger-facing interpretation, predicted crowd conditions can be represented as:

🟢 **Low**

🟡 **Medium**

🔴 **High**

The exact thresholds used to create these categories must be documented with the final experiment.

---

# 5. Overall BusSure Architecture

```text
                 PUBLIC TRANSPORT DATA
                          │
              ┌───────────┴───────────┐
              │                       │
       Operational Data         Passenger Data
              │                       │
       GTFS / AVL Data       Boarding / Alighting
              │                       │
              ▼                       ▼
        Preprocessing            Preprocessing
              │                       │
              ▼                       ▼
        Network Graph            Network Graph
              │                       │
              ▼                       ▼
            DCRNN                   ST-GCN
              │                       │
              ▼                       ▼
      Travel-Time / ETA         Passenger Load
              │                       │
              └───────────┬───────────┘
                          │
                          ▼
                Journey Reliability
                          │
                          ▼
               Passenger Information
```

---

# 6. Datasets Used

Two main public transport datasets are used for the current BusSure experiments.

Large raw datasets do not need to be stored directly inside this repository. Their original download sources are provided below for reproducibility.

---

## 6.1 SUNT Dataset

### Purpose

**Bus travel-time prediction**

### Model

**DCRNN**

The SUNT dataset provides public transport operational/network information suitable for analysing bus movement and travel-time behaviour.

The dataset contains transport information used to construct temporal observations and network relationships required for travel-time modelling.

### Dataset Source

**Mendeley Data**

https://data.mendeley.com/datasets/85fdtx3kr5/1

### Use in BusSure

The dataset is processed to construct:

- Network nodes
- Network connections
- Temporal observations
- Historical travel sequences
- Travel-time prediction targets

These processed data are then used to train and evaluate the DCRNN model.

---

## 6.2 SSA_StopBusTimeSeries_5

### Purpose

**Passenger load / crowd prediction**

### Model

**ST-GCN**

This dataset provides bus-stop time-series information containing passenger-flow information suitable for crowd prediction.

Relevant information includes:

- Passenger boarding
- Passenger alighting
- Passenger load
- Stop-level observations
- Temporal observations

### Dataset Source

**Hugging Face**

https://huggingface.co/datasets/labiaufba/SSA_StopBusTimeSeries_5

### Use in BusSure

Passenger observations are transformed into temporal sequences and associated with the public transport network.

These sequences are used to train the ST-GCN model to predict passenger load.

Predicted load is subsequently interpreted as:

```text
Low Crowd
Medium Crowd
High Crowd
```

for passenger-facing information.

---

# 7. Data Preprocessing

The preprocessing pipeline includes the following stages where applicable:

1. Load the raw transport data.
2. Inspect missing and invalid observations.
3. Parse date and time information.
4. Arrange observations chronologically.
5. Map records to stops, routes or segments.
6. Construct graph nodes and edges.
7. Generate temporal features.
8. Generate historical input sequences.
9. Construct prediction targets.
10. Split data into training, validation and test sets.

## Preventing Data Leakage

Transport data are time-dependent.

Therefore, where appropriate, the dataset is split chronologically so that future observations do not unintentionally appear in the training data.

Any preprocessing parameters learned from data should be obtained from the training set and subsequently applied to validation and test sets.

---

# 8. Experimental Evaluation

The AI models are evaluated quantitatively rather than evaluating only the final user interface.

---

## 8.1 Travel-Time Prediction

The DCRNN travel-time model is evaluated primarily using:

### Mean Absolute Error — MAE

```text
MAE = (1/n) Σ |Actual - Predicted|
```

MAE measures the average absolute difference between predicted and actual travel time.

A lower MAE indicates better performance.

### Root Mean Squared Error — RMSE

```text
RMSE = √[(1/n) Σ(Actual - Predicted)²]
```

RMSE gives greater penalty to large prediction errors.

A lower RMSE indicates better performance.

---

## 8.2 Passenger Load Prediction

Passenger-load prediction can be evaluated using:

- MAE
- RMSE

When passenger load is transformed into crowd classes:

**Low / Medium / High**

classification performance is evaluated using:

- Accuracy
- Precision
- Recall
- F1-score
- Confusion Matrix

---

# 9. Experimental Results

Only results obtained from completed experiments should be reported here.

## 9.1 Travel-Time Prediction

| Model | MAE | RMSE | Evaluation Data |
|---|---:|---:|---|
| Baseline | To be updated | To be updated | Same test split |
| DCRNN | To be updated | To be updated | Same test split |

---

## 9.2 Passenger Load Prediction

| Model | MAE | RMSE | Evaluation Data |
|---|---:|---:|---|
| Baseline | 3.052 | 6.276 | Same test split |
| ST-GCN | 2.534| 4.807 | Same test split |

---

## 9.3 Crowd Classification

| Model | Accuracy | F1-score |
|---|---:|---:|
| Baseline | 0.9276 | 0.9256 |
| ST-GCN-derived crowd classes | 0.8629 | 0.8632 |

> Final numbers will be added after verifying the corresponding saved experiment, data split and evaluation configuration.

---

# 10. Baseline Comparison

A proposed model should not be evaluated only by reporting its own performance.

BusSure therefore compares the proposed models against appropriate baseline approaches.

For a fair comparison, models must use:

- The same dataset
- The same training/validation/test split
- The same prediction target
- The same evaluation metrics

For example:

```text
Baseline Model
       │
       ├── MAE
       └── RMSE

          VS

Proposed DCRNN
       │
       ├── MAE
       └── RMSE
```

Similarly, crowd prediction baselines should be compared with ST-GCN under the same experimental conditions.

Only baseline models that have actually been executed will be reported in the final results.

---

# 11. Generalization Evaluation

Good performance on familiar observations does not automatically mean that a model will perform well on unseen transport conditions.

BusSure therefore treats **generalization** as an experimental research question.

The following evaluations are considered where supported by the dataset.

## 11.1 Unseen Time Periods

Train the model using earlier observations and evaluate it using later unseen observations.

This tests whether the model can predict future transport behaviour rather than memorizing historical samples.

## 11.2 Unseen Routes / Segments

Where the dataset permits, routes or segments can be excluded during training and used during evaluation.

This tests whether the learned model can transfer to parts of the network that were not directly observed during training.

## 11.3 Different Operating Conditions

Performance can be compared across available conditions such as:

- Peak hours
- Off-peak hours
- Weekdays
- Weekends
- Different levels of congestion

when the necessary information is available.

## 11.4 Cross-Network Evaluation

BusSure is designed so that its modelling pipeline can potentially be adapted to different public transport networks.

However:

> **Adaptability does not automatically mean proven cross-city accuracy.**

Performance in another city/network must be experimentally evaluated before claiming cross-city generalization.

---

# 12. Explainability and Journey Reliability

BusSure aims to provide passengers with information that is easier to understand than a single raw prediction.

Instead of displaying only:

```text
Predicted Travel Time = X minutes
```

the final system aims to provide information such as:

```text
Estimated Travel Time
Expected Arrival / Journey Range
Crowd Level
Journey Reliability
Potential Delay Factors
Alternative Journey Information
```

The travel-time and crowd predictions therefore act as inputs to a higher-level journey reliability layer.

Any explanation method used in the final implementation will be documented together with its methodology.

BusSure will not describe a factor as the **cause** of a delay unless causal evidence has actually been established.

---

# 13. Research Foundation and Related Work

The following peer-reviewed journal/research articles provide the main research foundation for BusSure. The selected studies cover bus travel-time prediction, graph-based spatio-temporal modelling, passenger-flow and occupancy prediction, model generalization, and explainable bus-delay analysis.

---

## 1. Adaptive Physics-Informed Machine Learning for Bus Travel Time Prediction: Solving the Peak Prediction Problem

**Year:** 2026  
**Journal:** Applied Soft Computing  
**Type:** Journal Research Article  
**Area:** Bus travel-time prediction  
**Method:** Physics-Informed LSTM (Phy-LSTM) with an adaptive Generalist-Specialist framework

**Relevance to BusSure:**  
Provides a recent reference for bus travel-time prediction under both normal and rare peak-delay conditions. The study is particularly relevant because it was evaluated using real GPS observations collected under heterogeneous Indian traffic conditions.

**DOI:**  
https://doi.org/10.1016/j.asoc.2026.115435

**Open-access article:**  
https://www.sciencedirect.com/science/article/pii/S1568494626008835

---

## 2. Short-Term Bus Passenger Flow Prediction Based on Graph Diffusion Convolutional Recurrent Neural Network

**Year:** 2023  
**Journal:** Applied Sciences  
**Type:** Journal Research Article  
**Area:** Bus passenger-flow prediction  
**Method:** Diffusion Convolutional Recurrent Neural Network (DCRNN)

**Relevance to BusSure:**  
Demonstrates how diffusion graph convolution and recurrent neural networks can jointly capture spatial and temporal dependencies in a bus network. It provides an important methodological reference for graph-based spatio-temporal modelling in BusSure.

**DOI:**  
https://doi.org/10.3390/app13084910

**Open-access article and PDF:**  
https://www.mdpi.com/2076-3417/13/8/4910

---

## 3. BAT-Transformer: Prediction of Bus Arrival Time with Transformer Encoder for Smart Public Transportation System

**Year:** 2024  
**Journal:** Applied Sciences  
**Type:** Journal Research Article  
**Area:** Bus arrival-time prediction  
**Method:** Transformer Encoder with multi-head attention

**Relevance to BusSure:**  
Provides a deep-learning reference for modelling temporal dependencies in bus arrival-time data and demonstrates the use of attention-based models for improving arrival-time prediction.

**DOI:**  
https://doi.org/10.3390/app14209488

**Open-access article and PDF:**  
https://www.mdpi.com/2076-3417/14/20/9488

---

## 4. Transformer Based Arrival Time Prediction for a Target Bus Stop Using Single Stop Information

**Year:** 2026  
**Journal:** Journal of The Korea Society of Computer and Information  
**Type:** Journal Research Article  
**Area:** Bus arrival-time / destination ETA prediction  
**Method:** Transformer Encoder

**Relevance to BusSure:**  
Predicts travel time for individual sections between bus stops and calculates destination-stop ETA by accumulating the predicted section travel times. This is closely related to BusSure's journey and stop-to-stop travel-time prediction objective.

**DOI:**  
https://doi.org/10.9708/jksci.2026.31.03.037

**Article page:**  
https://journal.kci.go.kr/jksci/archive/articleView?artiId=ART003317581

**Direct PDF:**  
https://journal.kci.go.kr/jksci/archive/articlePdf?artiId=ART003317581

---

## 5. Generalization Strategies for Improving Bus Travel Time Prediction Across Networks

**Year:** 2024  
**Journal:** Journal of Urban Management  
**Type:** Journal Research Article  
**Area:** Bus travel-time prediction and model generalization

**Relevance to BusSure:**  
Investigates whether bus travel-time models can generalize to unseen routes and different public-transport networks. It uses standardized open transport information including GTFS and GTFS-Realtime and directly supports BusSure's generalization evaluation.

**DOI:**  
https://doi.org/10.1016/j.jum.2024.05.002

**Open-access article:**  
https://www.sciencedirect.com/science/article/pii/S222658562400061X

---

## 6. A Causality-Based Explainable AI Method for Bus Delay Propagation Analysis

**Year:** 2025  
**Journal:** Communications in Transportation Research  
**Type:** Journal Research Article  
**Area:** Bus delay propagation and Explainable AI  
**Method:** Causal discovery and causality-aware Shapley-value analysis

**Relevance to BusSure:**  
Provides a research foundation for understanding how delays propagate through connected bus stops and how operational, calendar, and weather-related factors contribute to delay. It supports the explainability and journey-reliability components of BusSure.

**DOI:**  
https://doi.org/10.1016/j.commtr.2025.100178

**Open-access article + downloadable PDF:**  
https://www.sciopen.com/article/10.1016/j.commtr.2025.100178?issn=2097-5023

---

## 7. Conditional Forecasting of Bus Travel Time and Passenger Occupancy with Bayesian Markov Regime-Switching Vector Autoregression

**Year:** 2025  
**Journal:** Transportation Research Part B: Methodological  
**Type:** Journal Research Article  
**Area:** Bus travel-time and passenger-occupancy forecasting  
**Method:** Bayesian Markov Regime-Switching Vector Autoregression

**Relevance to BusSure:**  
This study is particularly relevant because it jointly investigates two major types of information considered by BusSure: bus travel time and passenger occupancy. It also considers prediction uncertainty rather than providing only deterministic point estimates.

**DOI:**  
https://doi.org/10.1016/j.trb.2024.103147

**Open-access publisher article:**  
https://www.sciencedirect.com/science/article/pii/S0191261524002716

---

## 8. Development and Evaluation of Frameworks for Real-Time Bus Passenger Occupancy Prediction

**Year:** 2023  
**Journal:** International Journal of Transportation Science and Technology  
**Type:** Journal Research Article  
**Area:** Passenger occupancy prediction  
**Methods:** Linear Regression and Random Forest

**Relevance to BusSure:**  
Provides a direct research foundation for predicting passenger occupancy of individual buses at future stops using operational information, Automatic Passenger Counter data, and weather information.

**DOI:**  
https://doi.org/10.1016/j.ijtst.2022.03.005

**Open-access article:**  
https://www.sciencedirect.com/science/article/pii/S2046043022000296

---

## 9. Short-Term Passenger Flow Prediction Using a Bus Network Graph Convolutional Long Short-Term Memory Neural Network Model

**Year:** 2023  
**Journal:** Transportation Research Record  
**Type:** Journal Research Article  
**Area:** Bus passenger-flow prediction  
**Method:** Bus Network Graph Convolutional LSTM (BNG-ConvLSTM)

**Relevance to BusSure:**  
Closely supports BusSure's crowd-prediction research because the bus network is represented as a graph and the model learns both spatial relationships among stops and temporal passenger-flow patterns.

**DOI:**  
https://doi.org/10.1177/03611981221112673

**Open-access full article:**  
https://journals.sagepub.com/doi/full/10.1177/03611981221112673

**PDF:**  
https://journals.sagepub.com/doi/pdf/10.1177/03611981221112673

---

## 10. TMS-GNN: Traffic-Aware Multistep Graph Neural Network for Bus Passenger Flow Prediction

**Year:** 2025  
**Journal:** Transportation Research Part C: Emerging Technologies  
**Type:** Journal Research Article  
**Area:** Bus passenger-flow forecasting  
**Method:** Traffic-Aware Multistep Graph Neural Network (TMS-GNN)

**Relevance to BusSure:**  
Supports BusSure's spatio-temporal passenger crowd modelling because it represents relationships among bus stops while considering temporal passenger-flow behaviour and traffic information.

**DOI:**  
https://doi.org/10.1016/j.trc.2025.105107

**Free final published version (CC BY):**  
https://research.tudelft.nl/en/publications/tms-gnn-traffic-aware-multistep-graph-neural-network-for-bus-pass/---

# 14. Relationship Between Existing Research and BusSure

The research papers above provide the scientific foundation for different components of BusSure.

| Research Area | Related Papers |
|---|---|
| Bus travel-time / ETA prediction | Papers 1, 3–4 |
| Graph-based and spatio-temporal modelling | Papers 2, 9–10 |
| Model generalization across transport networks | Paper 5 |
| Bus delay propagation and explainability | Paper 6 |
| Travel time + passenger occupancy | Paper 7 |
| Passenger occupancy prediction | Papers 7–8 |
| Passenger flow / crowd-related prediction | Papers 2, 9–10 |

These papers are **research references**.

The research papers above provide the scientific foundation for different components of BusSure.

They do not imply that BusSure implements every model described in these studies.

The current primary BusSure models are:

```text
Travel-Time Prediction → DCRNN

Passenger Crowd Prediction → ST-GCN
```

The literature is used to:

- understand existing approaches,
- identify research gaps,
- justify modelling choices,
- design experiments,
- and establish suitable comparisons.

---

# 15. Reproducibility

An important objective of the project is to make the experiments reproducible.

A researcher should be able to understand:

```text
Dataset
   ↓
Preprocessing
   ↓
Graph Construction
   ↓
Train / Validation / Test Split
   ↓
Model Configuration
   ↓
Training
   ↓
Evaluation
   ↓
Results
```

The repository will therefore provide the relevant implementation files as development progresses.

Recommended repository structure:

```text
Busai/
│
├── README.md
├── requirements.txt
│
├── data/
│   └── README.md
│
├── preprocessing/
│   ├── travel_time_preprocessing.py
│   └── crowd_preprocessing.py
│
├── models/
│   ├── dcrnn/
│   └── stgcn/
│
├── training/
│   ├── train_dcrnn.py
│   └── train_stgcn.py
│
├── evaluation/
│   ├── evaluate_travel_time.py
│   └── evaluate_crowd.py
│
├── configs/
│   ├── dcrnn_config.yaml
│   └── stgcn_config.yaml
│
└── results/
    ├── travel_time/
    └── crowd/
```

For each final experiment, the following information should be documented:

- Dataset source
- Dataset version
- Features used
- Target variable
- Data-cleaning procedure
- Graph-construction method
- Train/validation/test split
- Random seed, where applicable
- Model architecture
- Hyperparameters
- Batch size
- Number of epochs
- Learning rate
- Optimizer
- Evaluation metrics
- Final results

---

# 16. Limitations

The current BusSure research has several limitations.

1. The models are currently evaluated using specific public transport datasets. Performance on these datasets does not automatically guarantee the same accuracy in every city.

2. Public transport datasets differ in their available features, data quality, stop structure and temporal resolution.

3. Passenger crowd prediction depends on the availability and quality of boarding, alighting and passenger-load information.

4. Crowd categories such as **Low, Medium and High** depend on the thresholds selected for the experiment.

5. Unusual events such as accidents, road closures, strikes, extreme weather or large public events may not be sufficiently represented in historical training data.

6. Cross-city generalization requires dedicated evaluation on additional transport networks.

7. Real-time deployment would depend on the availability and reliability of live GPS/AVL and passenger information.

---

# Project Goal

BusSure aims to move public transport information beyond:

> **“When will my bus arrive?”**

toward:

> **“How long is my journey likely to take, how crowded may the bus be, how reliable is that information, and what can help me make a better journey decision?”**
