# Somtomorrow

A next-gen Somtoday webapp that works how students want it to work.  
Built in Flask and Jinja.

It's currently very much a prototype

## Run yourself

clone the repo  
cd into the repo  
run `pip install -r requirements.txt` to install stuff  
run `py main.py` (or `python3 main.py` or `python main.py` you know!)  
visit `localhost:5000` and there it is!

## To-do

Yeah it's a lot...

### Other

- [x] Add better error handling at login (from Vik)
- [ ] Add some caching and async stuff so users do not have to wait for the paige to load they just have to wait for the content to load 

### Auth

- [x] Finish auth with school/username/password (with Vik)
- [ ] Add long term login with refresh tokens
- [ ] Maybe look into using the Somtoday login after all with a kind of redirect?
- [ ] Add some kind of loading screen when getting the tokens from Vik!

### Features

- [ ] Add notification system for grades (easy) and schedules (certainly impossible) (with Firebase???)
- [x] Add avatars (identicon?)

### Pages

#### Dashboard

- [ ] Latest grades
- [ ] Future homework
- [ ] Schedule of current day

#### Grades

- [ ] Use new Som API for grades  
    ```
    api_urls = [
        f"https://api.somtoday.nl/rest/v1/geldendexamendossierresultaten/leerling/{staticmethod}?type=Toetskolom&type=DeeltoetsKolom&type=Werkstukcijferkolom&type=Advieskolom&additional=vaknaam&additional=resultaatkolom&additional=naamalternatiefniveau&additional=vakuuid&additional=lichtinguuid&sort=desc-geldendResultaatCijferInvoer",
        "https://api.somtoday.nl/rest/v1/geldendvoortgangsdossierresultaten/leerling/{student_id}?type=Toetskolom&type=DeeltoetsKolom&type=Werkstukcijferkolom&type=Advieskolom&additional=vaknaam&additional=resultaatkolom&additional=naamalternatiefniveau&additional=vakuuid&additional=lichtinguuid&sort=desc-geldendResultaatCijferInvoer"
    ]
    ```
    - [ ] Add new data that the this API provides
- [x] Finish current grade page
  - [x] Extra info on click
  - [x] Finish styles
- [ ] Add reports
- [x] Add herkansingen
  - [ ] Clean up the herkansing data and make it a list?
- [ ] Add future tests (empty test columns)
- [ ] Add grade page for each subject
- [ ] Add *deeltoetsen*
- [ ] Add stats
  - [ ] Timeline for each grade
  - [ ] Histograph for all grades
  - [ ] Median, average and stuff
