# 

Knowledge Graph Foundry - production-grade, data-science-driven system that builds and continuously maintains Neo4j knowledge graphs with purpose-driven construction, drift detection and GraphRAG optimization

> **Note**: Generated with copier-data-science template v1.2+
> For template documentation, visit [copier-data-science](https://github.com/stellarshenson/copier-data-science)

## Quick Start

```bash
make install
```

## Makefile Targets

- `make install` - Create environment and install package
- `make test` - Run tests
- `make lint` / `make format` - Check / fix code style
- `make build` - Build distributable wheel
- `make clean` - Remove compiled files and caches
- `make help` - Show all available targets

## Best Practices

- **Notebooks**: Name with number prefix, initials, description - `01-jqp-data-exploration.ipynb`
- **Data**: Keep `raw/` immutable, use `interim/` for transforms, `processed/` for final datasets
- **Source code**: Refactor reusable notebook code into `src/knowledge_graph_foundry/` modules
- **Models**: Store trained models in `models/` with clear naming

## Project Organization

```
├── Makefile           <- Makefile with convenience commands
├── README.md          <- The top-level README for developers
├── data
│   ├── external       <- Data from third party sources
│   ├── interim        <- Intermediate data that has been transformed
│   ├── processed      <- The final, canonical data sets for modeling
│   └── raw            <- The original, immutable data dump
│
├── models             <- Trained and serialized models
├── notebooks          <- Jupyter notebooks
├── pyproject.toml     <- Project configuration and dependencies
├── references         <- Data dictionaries, manuals, explanatory materials
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures
├── tests              <- Test files
└── src
    └── knowledge_graph_foundry   <- Source code for this project
        ├── __init__.py
        ├── config.py      <- Configuration variables
        ├── dataset.py     <- Data download/generation scripts
        ├── features.py    <- Feature engineering code
        ├── modeling
        │   ├── predict.py <- Model inference
        │   └── train.py   <- Model training
        └── plots.py       <- Visualization code
```
