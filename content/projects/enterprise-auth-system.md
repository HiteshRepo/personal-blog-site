---
title: "Enterprise Authentication, Authorization and User Management"
organization: "Current Role"
role: "Senior Software Engineer"
startDate: "2024-11-01"
endDate: "2025-06-01"
techStack: ["Go", "Chi Router", "OpenAPI", "CosmosDB", "Auth0", "Azure Key Vault", "EventHub", "Azure Data Explorer", "OpenTelemetry", "Docker"]
featured: true
description: "Comprehensive user management microservice for enterprise-scale multi-tenant SaaS platform"
weight: 2
---

## Project Overview

Developed and maintained a comprehensive user management microservice handling authentication, authorization, and user lifecycle management for enterprise-scale multi-tenant SaaS platform. Built to serve thousands of users across multiple organizations with complex authorization requirements.

## Key Achievements

### Authentication & Authorization System
- Built robust REST APIs for user management, role-based access control (RBAC), and organization onboarding using Go, Chi router, and OpenAPI specifications
- Integrated Auth0 authentication platform with custom role and permission management
- Supported social connections, machine-to-machine authentication, and enterprise identity providers
- Developed sophisticated authorization system with hierarchical permissions and policy-based access control

### Database & Data Architecture
- Designed and implemented CosmosDB data layer with optimized queries for user, role, and organization management
- Implemented proper partitioning strategies across multiple containers for sub-second response times
- Built efficient data models with optimized partition keys and query patterns

### Enterprise Features
- Implemented fine-grained workload tenant permissions for Azure and Kubernetes services
- Built organization lifecycle management including automated onboarding and user invitations
- Developed group management and complete organization deletion workflows
- Created service account management with client credentials flow for machine-to-machine authentication

### Platform Integration
- Integrated Azure Key Vault for secrets management
- Connected EventHub for event streaming and Azure Data Explorer (ADX) for analytics
- Built automated organization onboarding with Auth0 integration and custom domain validation
- Implemented Microsoft tenant discovery capabilities

### Quality & Observability
- Implemented comprehensive testing suite including unit tests, integration tests with CosmosDB
- Developed table-driven test patterns achieving high code coverage
- Established observability patterns using OpenTelemetry and structured logging with Clues
- Built comprehensive error handling with context propagation

## Technical Highlights

- **Authorization Matrix**: Supporting 100+ permissions across different workload types (Azure, Kasten/Kubernetes)
- **Multi-tenant Architecture**: Scalable design serving thousands of users across multiple organizations
- **Performance**: Sub-second response times with optimized CosmosDB queries
- **Testing Excellence**: Comprehensive unit and integration testing with GoMock

## Technologies Used

- **Backend**: Go, Chi Router, OpenAPI/Swagger code generation
- **Authentication**: Auth0, RBAC, policy-based authorization
- **Database**: Azure CosmosDB, NoSQL, complex queries, partitioning
- **Cloud Services**: Azure Key Vault, EventHub, Azure Data Explorer (ADX)
- **Architecture**: Microservices, multi-tenant SaaS, event-driven architecture
- **Observability**: OpenTelemetry, structured logging, comprehensive error handling
- **Testing**: Unit tests, integration tests, table-driven patterns, GoMock
- **DevOps**: Containerization, auto-generated Dockerfiles