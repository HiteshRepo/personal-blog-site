---
title: "Canario (Corso) - Microsoft 365 Backup Solution"
organization: "Open Source Project"
role: "Core Contributor"
startDate: "2024-01-01"
endDate: "2024-10-01"
techStack: ["Go", "Microsoft Graph API", "CLI", "AWS S3", "Docker", "Microsoft 365", "Azure"]
featured: true
description: "Open-source data protection engine for Microsoft 365 environments"
githubUrl: "https://github.com/alcionai/corso"
weight: 2
---

## Project Overview

Developed an enterprise-grade, open-source data protection engine for Microsoft 365 environments, creating the first comprehensive backup solution addressing critical M365 data protection needs for IT administrators.

## Key Technical Achievements

### Backend Development
- Developed enterprise-grade backup and restore system for Microsoft 365 services (Exchange, OneDrive, SharePoint, Teams)
- Implemented CLI interface with comprehensive command structure supporting backup, restore, export, and debug operations
- Built modular architecture with clear separation between API layer (`/pkg`), CLI controller, and internal services
- Designed repository abstraction layer supporting multiple storage backends (S3, filesystem)

### Microsoft 365 Integration
- Integrated with Microsoft Graph API for seamless access to M365 data
- Implemented service-specific backup handlers for:
  - **Exchange**: Email backup and restore
  - **OneDrive**: File backup and synchronization
  - **SharePoint**: Site and document library protection
  - **Teams**: Conversation and channel data backup
- Built robust authentication and authorization flows for Microsoft 365 environments

### Enterprise Features
- Developed comprehensive backup lifecycle management (create, list, delete, restore)
- Implemented data export functionality with multiple format support
- Built advanced debugging tools for troubleshooting backup operations
- Created extensive test coverage including end-to-end testing infrastructure
- Designed for enterprise scalability and security requirements

### Production Readiness
- Currently in Beta with active community engagement
- Built production-ready architecture with enterprise security standards
- Implemented comprehensive error handling and logging
- Created CI/CD pipeline with automated dependency management

## Technical Skills Demonstrated

- **Languages**: Go (advanced CLI applications, microservices architecture)
- **Cloud Integration**: Microsoft 365, Azure, AWS S3
- **API Integration**: Microsoft Graph API, RESTful services
- **Architecture**: CLI applications, microservices, repository pattern
- **Testing**: Unit testing, end-to-end testing, test-driven development
- **DevOps**: Git, Docker, CI/CD, automated dependency management

## Project Impact

- Created the **first open-source solution** addressing critical M365 data protection needs
- Enabled IT administrators to have full control over Microsoft 365 data backup strategies
- Built for enterprise scalability supporting large-scale M365 deployments
- Active community engagement with ongoing development and feature requests

## Technologies Used

- **Core Language**: Go
- **Microsoft Integration**: Microsoft Graph API, Microsoft 365 services
- **Storage Backends**: AWS S3, filesystem abstraction
- **Architecture**: CLI-first design, modular microservices
- **Testing Framework**: Comprehensive unit and end-to-end testing
- **DevOps**: Docker containerization, CI/CD pipelines