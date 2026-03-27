---
title: "Index and Search Petabytes of Data"
organization: "Improving"
role: "Senior Data Engineer"
startDate: "2025-07-01"
techStack: ["Databricks", "Apache Spark", "Delta Lake", "Azure Event Hubs", "Go", "Python", "PySpark", "CosmosDB", "Azure Container Apps", "Elasticsearch", "Kibana", "TypeScript", "Node.js", "Pulumi", "Azure OpenAI", "RAG"]
featured: true
description: "End-to-end data pipeline infrastructure for M365 workload events processing with AI-powered semantic search"
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

### Pipeline Services

- **Data Ingestion Service**: Event processing service publishing to multiple Event Hubs (backup, backfill, retention, recovery points, threats) with tenant resolution and validation
- **Data Discovery Service**: Go-based REST API for browsing indexed metadata and data discovery with filtering capabilities and AI-enhanced natural language search

### AI-Powered Semantic Search

- Implemented RAG (Retrieval Augmented Generation) pipeline for semantic search over backed-up M365 data
- Backup data stored in embedded form in CosmosDB using hybrid vector + keyword search capabilities
- Natural language queries translated to structured metadata filters using Azure OpenAI Chat Completions
- Filter generation prompt uses system prompt combined with few-shot examples for reliable, structured output
- Enables users to search petabytes of backup data using plain English queries without knowledge of underlying schema

### AI Developer Tooling

- **Elastic Dashboard Changelog**: Python script that diffs `.ndjson` Kibana dashboard files (unreadable in standard GitHub diffs) and feeds the structured diff to Anthropic API to generate a human-readable changelog
- **Security Fix Automation**: Local AI skill that ingests Cycode security findings and applies targeted fixes using LLM-assisted code correction with full finding context

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
- **AI/ML**: Azure OpenAI, RAG pipeline, CosmosDB hybrid vector search, few-shot prompting, semantic metadata filter generation
- **DevOps**: Incident.io, automated alerting, operational runbooks
