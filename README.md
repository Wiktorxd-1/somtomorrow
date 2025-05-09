# Somtomorrow

A next-gen Somtoday webapp that works how students want it to work.  
Built in Flask and Jinja.

It's currently very much a prototype but it works and that's just amazing!

## Run yourself

- clone the repo  
- cd into the repo  
- run `pip install -r requirements.txt` to install stuff  
- run `flask --app main run` (or `python main.py`)  
- visit `localhost:5000` and there it is!

## To-do

Yeah it's a lot...

### Auth

- [ ] Add long term login with refresh tokens
- [ ] Maybe look into using the Somtoday login after all with a kind of redirect?
- [ ] Fix Authtoday

### Features

- [ ] Add notification system for grades (easy) and schedules (certainly impossible) (with Firebase???)

### Pages

#### Dashboard

- [ ] Better design

#### Grades

- [ ] Add reports
- [ ] Clean up the herkansing data and make it a list?
- [ ] Add future tests (empty test columns)
- [ ] Add grade page for each subject
- [ ] Add *deeltoetsen*
- [ ] Add calculator for which grade you need to get
- [ ] Add stats
  - [ ] Timeline for each grade
  - [ ] Histograph for all grades
  - [ ] Median, average and stuff

#### Planner

- [ ] Add info panel

#### Schedule

- [ ] Diffrent appointment types (*inidvidueel*, *rooster*, *examen*, *toets*)

#### Other

- [ ] Leermiddelen
