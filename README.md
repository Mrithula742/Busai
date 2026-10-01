# BusSure
### AI-Assisted Bus Journey Planning for Chennai

## Problem

Chennai bus passengers need to decide when to leave, which bus to take and which route suits them best. Timetables alone cannot explain actual delays or expected crowding.

## Proposed Solution

BusSure will compare journey options using the passenger’s location, destination and preferences.

Planned features:
- GPS-based vehicle tracking.
- Machine-learning-based travel-time prediction.
- Passenger occupancy and crowd estimation.
- Route recommendations based on time, crowding and transfers.
- Software simulation of vehicle delay-information sharing.


## Research References

Ten journal publications are listed below.

1. **[Development of an individualized multimodal trip planner for a MaaS system]
   (https://doi.org/10.1016/j.sftr.2025.100498)**  
   Sustainable Futures · 2025 · Journal article  
   Personalised journey planning. Proposed base paper; full-text review pending.

3. **[GPS-2-GTFS](https://doi.org/10.1016/j.simpa.2025.100780)**  
   Software Impacts · 2025 · Software journal article  
   Converts raw GPS readings into structured transit information.

4. **[From Raw GPS to GTFS: A Real-World Open Dataset for Bus Travel Time Prediction](https://doi.org/10.3390/data10080119)**  
   Data · 2025 · Dataset journal article  
   Provides the Astana dataset selected for travel-time experiments.

5. **[Data-driven analysis of run-level bus alighting patterns for accurate predictions and operational efficiency](https://doi.org/10.1016/j.ijtst.2025.06.006)**  
   International Journal of Transportation Science and Technology · 2025 · Journal article  
   Studies passenger alighting using Chennai electronic-ticketing records.

6. **[DeepSense-V2V](https://doi.org/10.1109/TVT.2025.3578349)**  
   IEEE Transactions on Vehicular Technology · 2025 · Journal article  
   Background research on vehicle-to-vehicle sensing and communication.

7. **[CPTOND-2025: National-Scale Bus-Metro Vector Dataset](https://doi.org/10.1038/s41597-025-06505-4)**  
   Scientific Data · 2026 · Journal data descriptor  
   Reference for organising bus and metro network information.

8. **[Bus user itinerary choice: Can crowding information help shift riders?](https://doi.org/10.1016/j.cstp.2025.101375)**  
   Case Studies on Transport Policy · 2025 · Journal article  
   Examines how crowding information influences journey choices.

9. **[Assessing public transport accessibility using GPS data](https://doi.org/10.1186/s12544-025-00733-w)**  
   European Transport Research Review · 2025 · Journal article  
   Supports location-based analysis of access to public transport.

10. **[A Comprehensive Vector Dataset of Bus Networks Across China for the Year 2024](https://doi.org/10.1038/s41597-025-04894-0)**  
   Scientific Data · 2025 · Journal data descriptor  
   Reference for representing bus routes, stops and connections.

11. **[Adaptive physics-informed machine learning for bus travel time prediction]
(https://doi.org/10.1016/j.asoc.2026.115435)**
    Applied Soft Computing · 2026 · Journal article
    Uses Phy-LSTM and XGBoost for bus travel-time prediction.



---

## Datasets

### Chennai MTC GTFS
**Purpose:** Route and timetable-based journey planning.

Contains routes, stops, trips and scheduled timings. It is an unofficial community-maintained feed and does not contain historical actual bus arrivals.

[Source repository](https://github.com/ungalsoththu/ChennaiGTFS) · [Download ZIP](https://github.com/ungalsoththu/ChennaiGTFS/raw/main/data/mtc-gtfs.zip)

### Astana Bus-Operation Data
**Purpose:** Initial travel-time prediction experiments.

Downloaded `segment_level_data.zip` and `gtfs_data.zip` from the dataset associated with Research Reference 3.

These records describe Astana, Kazakhstan. Chennai observations are needed to validate performance locally.

[Dataset and downloads](https://doi.org/10.5281/zenodo.15769359) · [Related paper](https://doi.org/10.3390/data10080119)

**Licence:** CC BY 4.0.

### Synthetic Static Crowding Data
**Purpose:** Test passenger-count calculations.

Created 3,000 simulated ticket transactions using Chennai GTFS route, trip and stop references:
- 1,000 Chennai One-style records.
- 2,000 conductor ETM-style records.

Passenger quantities and source proportions are simulation assumptions. No actual Chennai One or MTC ETM transactions were obtained.

Occupancy is calculated by adding boarding passengers and subtracting alighting passengers. Synthetic results demonstrate software behaviour, not real-world prediction accuracy.

[Research reference](https://doi.org/10.1016/j.ijtst.2025.06.006) · [Official MTC ticketing information](https://mtcbus.tn.gov.in/Home/facilities)

These sources motivate the design; they do not supply the generated passenger values.
