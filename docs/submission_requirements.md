# Final Project Code Submission Requirements

This document records the general code-submission requirements shown in the
course assignment page. It complements the project-specific requirements in
`PROJECT FINANCIAL MARKET ANALYTICS 3 -PHASES.docx`.

## Administrative details

- Submission deadline shown: **November 3 at 00:59** (year not shown in the
  source screenshot).
- Submission format: **one uploaded file**.
- Points available: **160**.
- The submitted file must be one compressed folder containing all required
  materials below.

## Required submission contents

### 1. Complete source code

- Include every script and notebook used for:
  - data cleaning;
  - feature engineering;
  - modelling;
  - evaluation; and
  - deployment.
- Include all helper modules, such as utility modules and packages under
  `src/`.

### 2. Deployment package

- Provide a working API implementation, such as FastAPI.
- The API must include:
  - routing;
  - input validation; and
  - model loading.
- Include every configuration file required to run the service locally.

### 3. Documentation

- Provide a clear `README.md` explaining how to run the complete project from
  end to end.
- Include a short deployment guide, either in the README or as a linked
  document.

### 4. Reproducibility files

- Provide a dependency specification, such as `requirements.txt`,
  `environment.yml`, or an equivalent project file.
- If Docker is used, include a `Dockerfile` and the instructions needed to use
  it. Docker is optional.

### 5. Outputs and artefacts

- Include saved trained models (for example `.pkl`, `.joblib`, or `.pt` files).
- Include fitted preprocessing objects such as scalers and encoders.
- Include final evaluation results relevant to this project, such as metrics
  tables and a backtest summary.
- Export and include plots used in the final report where appropriate. This is
  optional but recommended.

## Reproducibility and quality requirements

- The project must run in a clean environment.
- Do not rely on machine-specific local paths.
- Use relative paths such as `data/processed/...`; do not hard-code absolute
  paths.
- Make the final pipeline executable in a logical order:

  `preprocess -> train -> evaluate -> deploy`

- Remove unused code and duplicate files before submission; retain only
  relevant, functional material.
- Use consistent names for scripts and directories.
- Give saved model artefacts clear versions or labels, for example
  `model_v1.joblib`.

## Academic integrity and security

- Submitted code must be the student's own work, except for third-party
  libraries used under their applicable licences.
- Clearly cite external datasets, code snippets, and models in the README or
  in code comments.
- Do not include private keys, tokens, passwords, or other secrets in the
  submission.
- Load any required credentials through environment variables.
- Exclude credentials and local secret files from the submitted archive.

## Final submission checklist

- [ ] One compressed submission folder has been prepared.
- [ ] All cleaning, feature-engineering, modelling, evaluation, and deployment
      code is included.
- [ ] Helper modules and packages are included.
- [ ] The local API works and performs routing, validation, and model loading.
- [ ] Required API configuration files are included.
- [ ] The README contains end-to-end run instructions.
- [ ] Deployment instructions are included or linked.
- [ ] Dependencies are fully specified.
- [ ] The project has been tested in a clean environment.
- [ ] All runtime paths are relative and portable.
- [ ] The pipeline runs in the required logical order.
- [ ] Saved models and preprocessing objects are included and clearly labelled.
- [ ] Final metrics and the backtest summary are included.
- [ ] Report plots have been exported where useful.
- [ ] External datasets, snippets, libraries, and models are cited.
- [ ] Secrets are absent from the archive and ignored by version control.
- [ ] Unused or duplicate files have been removed.

## Source note

Recorded from the course page screenshot supplied on 2026-09-30. The original
page remains the authority if its requirements change.
