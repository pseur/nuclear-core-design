#!/bin/bash
pip install -U https://s3-us-west-2.amazonaws.com/ray-wheels/latest/ray-0.8.0.dev6-cp36-cp36m-manylinux1_x86_64.whl
pip install ray[tune]
pip install ray[rllib]
pip install ray[debug]
