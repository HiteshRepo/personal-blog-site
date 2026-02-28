---
title: "Index and Search Petabytes of Data"
organization: "Current Role"
role: "Senior Data Engineer"
startDate: "2025-07-01"
techStack: ["Databricks", "Apache Spark", "Delta Lake", "Azure Event Hubs", "Go", "Python", "PySpark", "CosmosDB", "Azure Container Apps", "Elasticsearch", "Kibana", "TypeScript", "Node.js", "Pulumi"]
featured: true
description: "End-to-end data pipeline infrastructure for M365 workload events processing"
weight: 1
---

## Project Overview

Architected and implemented comprehensive end-to-end data pipeline infrastructure for processing M365 workload events using modern data engineering technologies. Built scalable real-time processing systems handling high-volume streaming data with advanced analytics and search capabilities.

## Key Achievements

### Data Pipeline Infrastructure
- Architected end-to-end data pipeline processing M365 workload events using Databricks, Apache Spark, and Delta Lake
- Implemented high-volume streaming data processing with Event Hubs and Azure Container Apps
- Developed complex Databricks jobs for event processing, indexing, and content enrichment
- Implemented SCD2 (Slowly Changing Dimension Type 2) algorithms for historical data tracking and temporal data management

### Microservices Architecture
- **Discovery Service**: Go-based REST API for browsing indexed metadata across workload tenants, integrating with Databricks Unity Catalog and CosmosDB
- **Raw Data Ingestion Service**: Event processing service publishing to multiple Event Hubs (backup, backfill, retention, recovery points, threats) with tenant resolution and validation  
- **Workload Data Discovery Service**: RESTful APIs for data item discovery with filtering capabilities and AI-enhanced natural language search

### Observability & Monitoring
- Implemented comprehensive monitoring solutions using Elastic Stack (Elasticsearch, Kibana)
- Created custom dashboards for service metrics, performance monitoring, and operational insights
- Automated alerting and incident management via Incident.io integration
- Designed operational runbooks and failure models for production systems

### Infrastructure & Operations
- Designed detailed troubleshooting procedures and alert response protocols
- Created escalation paths for critical data pipeline components
- Infrastructure as Code implementation using Pulumi
- Integration with OpenAI for enhanced search capabilities

## Technologies Used

- **Data Processing**: Databricks, Apache Spark, Delta Lake, PySpark
- **Streaming**: Azure Event Hubs, real-time processing
- **Backend Development**: Go, Python, TypeScript/Node.js
- **Databases**: CosmosDB, Azure SQL Warehouse
- **Infrastructure**: Azure Container Apps, Pulumi (IaC)
- **Monitoring**: Elasticsearch, Kibana, Elastic Stack
- **AI/ML**: OpenAI integration for natural language search
- **DevOps**: Incident.io, automated alerting, operational runbooks