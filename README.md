# dmii-text-mining

The second group project of DM II: retrieving customer feedback from **Booking.com** (focused on a chosen location) and applying language processing, machine learning, and sentiment analysis to support data-driven marketing decisions.

---

## Title

**Enhancing Customer Experience and Brand Perception: Leveraging Data Science and Digital Marketing for a Leading Hotel Chain**

---

## Problem Statement

A reputable hotel brand known for its accommodations and hospitality has seen a decline in customer satisfaction scores and stagnation in brand perception. Despite its reputation, the chain struggles to meet evolving consumer expectations, with fewer repeat bookings and more negative online reviews. The goal is to revitalize customer experience and brand image through analysis of client feedback and development of a targeted marketing strategy.

---

## The Challenge

The main difficulty is understanding *why* satisfaction and perception are slipping. The chain has large amounts of feedback (online reviews, surveys, social media), but turning that into **actionable insights** is hard. Connecting analysis to **digital marketing strategy** needs collaboration between data science and marketing.

---

## Solution Approach

A joint effort between data science and digital marketing students, structured as follows.

### 1. Data Collection and Consolidation

- Gather customer feedback from diverse sources, including **online reviews from Booking.com** (and optionally other platforms).
- Structure data in a **unified format** for analysis and interpretation.

### 2. Sentiment Analysis and Text Mining

- Use **NLP** for sentiment analysis on review and feedback text.
- Identify **themes, sentiments, and recurring patterns**—both strengths and pain points.

### 3. Customer Segmentation and Profiling

- Apply **machine learning** to segment customers by preferences, demographics, and behaviour.
- Build **customer profiles** for distinct segments and their needs.

---

## Evaluation Criteria

| Deliverable        | Weight |
| ------------------ | -----: |
| Data Preparation   |    20% |
| Modeling (code)    |    30% |
| White Paper (5 pages) | 40% |
| Pitch Video (5 min)   | 10% |

---

## Required Analysis & Modeling

### 1) Descriptive and Exploratory Data Analysis (EDA)

- **Rating distribution:** Most common rating ranges; differences by country or region.
- **Word frequency:** Top words in positive vs. negative reviews (e.g. word clouds).
- **Review length:** Average length by rating or region.
- **Sentiment by location:** Cities or hotels with unusual sentiment patterns.

### 2) NLP + Advanced Machine Learning

**a) Sentiment analysis (supervised classification)**  
Train a model to predict whether a review is positive, negative, or neutral.

**b) Topic modeling (unsupervised learning)**  
Discover main themes in reviews without using labels.

**c) Aspect-based sentiment analysis (ABSA)**  
Identify sentiment toward specific aspects (room, location, service).

**d) Review helpfulness prediction**  
Predict whether a review will be seen as helpful (e.g. likes or helpful votes).

**e) User or review clustering**  
Group users with similar behaviour or opinions.

**f) Temporal analysis**  
How sentiment or topics change over time (e.g. improvements or recurring issues).

**g) Fake review detection (anomaly detection)**  
Flag reviews that may be fraudulent or manipulative.

---

## Data Source (this project)

- **Platform:** Booking.com  
- **Scope:** One or more **locations** (cities/regions/hotels) to be selected by the team, aligned with the hotel-chain use case above.

---

## Repository Contents

- `scraper-eu.py` — scraping / data collection script (name as in repo).
