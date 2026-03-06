# README

Created by: EPA133a Group 10

| Name                | Student Number |
|---------------------|----------------|
| Angelica Saglimbeni | 6556671        |
| Elena Deckert       | 6580300        |
| Finn Maingay        | 5415586        |
| Tadas Lukavičius    | 5525047        |
| Viola Clerici       | 6542034        |

## Introduction
This repository contains the code and report for Assignment 2 for the course *EPA133A Advance Simulation*. This assignment modifies a simple transport model to analyse the N1 highway in Bangladesh and simulate traffic behaviour based on bridge quality. Multiple scenarios are evaluated, and the script runs the simulation and generates visualisations of the results.

##### Repository Content

* *Assignment 2 Group 10 Report:* Report explaining data preprocessing, model design and experiment results for this assignment.
* *EPA133a-G10-A2*: Folder with code for this assignment where:
  * *data*: preprocessing of data in [data-preprocessing.ipynb](data/preprocessing/data-preprocessing.ipynb) and preprocessed data in [processed_data.csv](data/preprocessing/processed_data.csv)
  * *model*: model python files:
    * *components.py*: behaviour and characteristics of the model components are defined, including agents such as trucks and infrastructure elements such as bridges.
    * *model.py*: contains the BangladeshModel simulation design which is a subclass of Mesa Model. It reads the preprocessed data to generate the transport model. 
    * *model_run.py*: sets up the model run conditions and scenarios, calls the model and runs the scenario experiments without visualization.
    * *model_viz.py*: sets up the visualization, uses the SimpleCanvas element defined by *model.py*, calls the model and runs the visualization server.
  * *experiment*: stores the results of the scenario experiment in csvs.
    *  [experiment_viz.ipynb](data/preprocessing/data-preprocessing.ipynb): script to visualize the average speed per scenario and top bridges depending on scenario results.

##### 

##### How to run

Create and activate a virtual environment

In PyCharm, you can create a virtual environment by following the steps below:
1. Open the project in PyCharm
2. Go to Settings -> Project: epa133a -> Python Interpreter
3. Click "Add Interpreter"
4. Select "Add Local Interpreter"
5. Select Virtualenv Environment
6. Select New environment
7. Select Base interpreter as Python 3.11
8. Click OK and also close the settings with OK

Afterwards, you should see "Python 3.11" (epa133a) in the bottom-right corner of the PyCharm window.
To install the requirements, open a terminal/command line window in PyCharm and type:

```
    $ pip install -r requirements.txt
```

- Launch the simulation model with visualization

```
    $ python model_viz.py
```

- Launch the simulation model without visualization

```
    $ python model_run.py
```


To run the scenarios run  *model_run.py* and to visualise the model run *model_viz.py*. 

