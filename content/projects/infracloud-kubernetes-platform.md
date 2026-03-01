---
title: "Kubernetes Infrastructure & Platform Engineering"
organization: "Infracloud Technologies"
role: "Software Engineer"
startDate: "2022-08-01"
endDate: "2023-12-01"
techStack: ["Kubernetes", "Go", "Python", "Terraform", "DHCP", "TFTP", "Tinkerbell", "Bare Metal"]
description: "Bare metal Kubernetes cluster provisioning and management platform"
weight: 4
---

## Project Overview

Built a comprehensive bare metal Kubernetes cluster provisioning platform, developing custom controllers and reconciliation logic to manage cluster lifecycle on bare metal infrastructure.

## Key Achievements

- **Kubernetes Components**: Built custom Kubernetes controller, API server, and scheduler components for bare metal cluster management
- **Reconciliation Logic**: Developed state management system to ensure desired cluster configuration and handle cluster drift
- **Bootstrap Service**: Created service deployed on private bootstrap machines in client networks that pulled commands from centralized SaaS platform and reported status
- **Bare Metal Provisioning**: Implemented bare metal readiness detection using DHCP and TFTP protocols
- **Agent-based Architecture**: Developed agents installed on bare metal machines to handle cluster operations
- **Infrastructure Automation**: Leveraged Tinkerbell framework for automated bare metal provisioning workflows

## Technologies Used

- **Container Orchestration**: Kubernetes (custom controllers, API server, scheduler)
- **Programming**: Go, Python
- **Infrastructure**: Terraform, bare metal provisioning
- **Protocols**: DHCP, TFTP for network boot and discovery
- **Provisioning**: Tinkerbell framework
- **Architecture**: SaaS platform with distributed agent-based management