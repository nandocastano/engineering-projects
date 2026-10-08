# María: Farm Logistics on Palantir Foundry

Ontology-driven decision support for farm operations, built on Palantir Foundry and AIP for the Palantir Build Challenge. Walkthrough video: <https://youtu.be/ssvYMJInNas>. Juan Fernando Castaño and team.

## What it does

- **Ontology.** Farm entities and the sensor time series attached to them are modelled in Foundry's ontology, so the application, the analytics and the language model work from the same objects.
- **Triage.** AIP ranks and explains what needs attention, working on ontology objects instead of raw documents.
- **Protocols.** Recommended actions are drafted with reference to FAO guidance, so a reviewer can check them against a recognised source.

```
sensor time series + farm records → Foundry ontology → AIP triage → protocol draft checked against FAO guidance
```

## Scope

The application lives in a Foundry workspace and is not part of this repository. This repository holds the technical report, which describes the design as presented in the challenge walkthrough. No performance figures are reported because none were measured. Triage and protocols are decision support; a person remains responsible for the action.

## Contents

```
report/    technical report (PDF and LaTeX source)
```
