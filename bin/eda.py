#!/usr/bin/env python

######################################
# Imports
######################################

import hydra
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from omegaconf import DictConfig
from os.path import join as join_path
import pandas as pd
from pathlib import Path

######################################
# Main
######################################


def construct_network(
    edge_list: pd.DataFrame, from_col: str, to_col: str, len_component: int = 5
) -> nx.Graph:
    edges = edge_list.sort_values(from_col)

    G = nx.from_pandas_edgelist(
        edges, from_col, to_col, create_using=nx.Graph() 
    )

    for component in list(nx.connected_components(G)):
        if len(component) <= len_component:
            for node in component:
                G.remove_node(node)

    return G

def visualize_network(G: nx.Graph, output_dir: str) -> str:
    plt.figure(figsize=(7,7))
    plt.xticks([])
    plt.yticks([])

    nx.draw_networkx(G, pos=nx.spring_layout(G, seed=42), with_labels=False,
                        node_color='blue', cmap="Set2", node_size = 10)

    outfile = join_path(output_dir, "graph.png")
    plt.savefig(outfile)
    return outfile

def calculate_metrics(G: nx.Graph, output_dir: str) -> dict[float]:
    metrics = {}
    for metric_func in [
        nx.diameter, nx.radius, nx.average_clustering, nx.node_connectivity, 
        nx.degree_assortativity_coefficient, nx.degree_pearson_correlation_coefficient
    ]:
        metrics[metric_func.__name__] = metric_func(G)
    
    outfile = join_path(output_dir, "metrics.csv")
    pd.DataFrame(metrics, index=[0]).to_csv(outfile, index=False)
    return metrics

def log_results(
        tracking_uri: str, experiment_prefix: str, grn_name: str, edge_list_file: str, 
        network_plot: str, metrics: dict[float]
    ) -> None:
    import mlflow
    mlflow.set_tracking_uri(tracking_uri)

    experiment_name = f"{experiment_prefix}_eda"
    existing_exp = mlflow.get_experiment_by_name(experiment_name)
    if not existing_exp:
        mlflow.create_experiment(experiment_name)
    mlflow.set_experiment(experiment_name)

    mlflow.set_tag("grn", grn_name)

    mlflow.log_param("grn", grn_name)
    mlflow.log_param("edge_list_file_name", edge_list_file)

    for k in metrics:
        mlflow.log_metric(k, metrics[k])
            
    mlflow.log_artifact(network_plot)

    mlflow.end_run()

@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(config: DictConfig) -> None:
    """
    The main entry point for the plotting pipeline.

    Args:
        config (DictConfig):
            The pipeline configuration.
    """
    EXPERIMENT_PREFIX = config["experiment"]["name"]

    DATA_DIR = config["dir"]["data_dir"]
    PREPROCESS_DIR = config["dir"]["preprocessed_dir"]
    OUT_DIR = config["dir"]["out_dir"]

    GRN_NAME = config["grn"]["input_dir"]
    EDGE_LIST_FILE = config["grn"]["edge_list"]
    FROM_COL = config["grn"]["from_col"]
    TO_COL = config["grn"]["to_col"]

    TRACKING_URI = config["experiment_tracking"]["tracking_uri"]
    ENABLE_TRACKING = config["experiment_tracking"]["enabled"]

    input_dir = join_path(DATA_DIR, PREPROCESS_DIR, GRN_NAME)
    edge_list = pd.read_csv(join_path(input_dir, EDGE_LIST_FILE))

    G = construct_network(edge_list, FROM_COL, TO_COL)

    nx.draw_networkx(
        G,
        with_labels=False,
    )

    output_dir = join_path(DATA_DIR, OUT_DIR, GRN_NAME, "eda")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    network_plot = visualize_network(G, output_dir)
    metrics = calculate_metrics(G, output_dir)

    if ENABLE_TRACKING:
        log_results(
            TRACKING_URI, EXPERIMENT_PREFIX, GRN_NAME, EDGE_LIST_FILE, 
            network_plot, metrics
        )

if __name__ == "__main__":
    main()
