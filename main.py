#!/usr/bin/env python3
import csv
import json
import os
import re
from datetime import datetime, timedelta
from dateutil import relativedelta

import requests
from PIL import Image, ImageDraw, ImageFont


class promotion:
    def __init__(self, milpacID, rank, date):
        '''
        Handle promotion processing.
        Inputs:
            milpacID (int): Milpac ID of trooper being promoted.
            rank (str): Rank being promoted, short version (Ex: SGT).
            date (str): Date trooper is being promoted, in DD-MMM-YYYY format. (Ex: 25-Jan-2020)
        '''
        self.milpacID = milpacID
        self.rank = rank
        self.date = date

        with open("APIKey.txt") as file:
            self.APIKey = file.readline().replace("\n", "")
            
        self.rawTroopers = requests.get(
            f"https://api.7cav.us/v1/users/active",
            headers={"Authorization": f"Bearer {self.APIKey}"}
            ).json()["data"]["users"]

        # Trooper's basic information
        self.trooper = [i for i in self.rawTroopers if i["milpac_id"] == milpacID][0]
        
        self.userID = self.trooper["user_id"] # Trooper's forum ID

        with open("config.json") as file:
            self.config = json.load(file)

        # Config info about requested rank.
        self.requestedRank = [i for i in self.config["ranks"] if i["short"] == rank][0]

    def push(self):
        # EXECUTES EVERYTHING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        TIG = self.checkTIG()
        if TIG != True:
            print(TIG)
            return 0
        
        if self.checkNCOA() == False:
            print("Trooper does not meet NCOA requirements.")
            return 0

        self.promoCitation()
        self.ncoCitation()

        print("Approver: "+self.getApprover())
    
    def checkTIG(self):
        '''
        Checks Time In Grade (TIG) Requirement. One month is 30 days.
        Output:
            True (bool), if TIG met.
            If not met, dict with following:
                RequiredTIG (int): Required TIG, in months.
                TIG (int): Current TIG, in months.
                Eligible (str): Date eligible for requested promo.
        '''
        lastPromo = datetime.strptime(self.trooper["promotion_date"], "%Y-%m-%d %H:%M:%S")
        currentPromo = datetime.strptime(self.date, "%d-%b-%Y")
        reqTIG = self.requestedRank["RequiredTIG"]
        TIG = relativedelta.relativedelta(currentPromo, lastPromo).months
        # TIG = (currentPromo - lastPromo).month

        if reqTIG == 0: # Hadle no TIG Requirement
            return True
        elif TIG >= reqTIG: # Requirement met.
            return True
        else: # Requirement not met.
            return {
                "RequiredTIG": reqTIG,
                "CurrentTIG": TIG,
                "Eligible": str(lastPromo + (reqTIG * timedelta(days=30)))
            }
    
    def checkNCOA(self):
        # Checks for NCOA eligibility.

        # If NCOA check not requried, return a Null value.
        if self.requestedRank["CheckNCOA"] == False:
            return None

        serviceRecord = requests.get(
            f"https://api.7cav.us/v1/user/{self.userID}/records",
            headers={"Authorization": f"Bearer {self.APIKey}"}
        ).json()["data"]

        p2, p1, old = False, False, False
        for s in serviceRecord:
            entry = s["details"].lower()
            if any(e in entry for e in ["ncoa warrior leadership course", "ncoa-wlc"]): # Check for any NCOA graduation.
                if "phase ii" in entry: # Check for phase 2.
                    p2 = True
                elif "phase i" in entry: # Check for phase 1.
                    p1 = True
                else: # If phase 1 and 2 not found. Assume old system.
                    old = True

        if old == True:
            return True
        elif p1 == True and p2 == True:
            return True
        else:
            return False

    def getApprover(self):     
        # Gets promotion approver.
        rankApprover = self.requestedRank["Approver"]
        regex = re.findall(r"(\w)/(\d-7)", self.trooper["primary_position"])
        if regex == False:
            return None
        else:
            company = "/".join(regex[0])
            battalion = regex[0][1]

        def findByBillet(billet):
            user = [i for i in self.rawTroopers if i["primary_position"] == billet][0]
            realName = user["real_name"]
            forumName = user["username"]
            return f"{realName} | @{forumName}"

        if rankApprover == False:
            return "N/A"
        elif rankApprover == "RTC":
            return "Recruit Training Command"
        elif rankApprover == "S1":
            return "S1 Department"
        elif rankApprover == "Company":
            return findByBillet(f"Commander {company}")
        elif rankApprover == "Battalion":
            return findByBillet(f"Battalion Commander {battalion}")
        elif rankApprover == "COS":
            return findByBillet("Chief of Staff")
        elif rankApprover == "GOA":
            return findByBillet("Regimental Commander")

    def folderName(self):
        # Get name of trooper's citation folder.
        name = self.trooper["real_name"].split(" ")
        return "-".join([name[-1]] + name[:-1]).lower()

    def ordinalIndicator(self, num):
            '''
            Take number and output string w/ ordinal indicator attached
            Inputs:
                num (int): Number to be formatted
            Output (str): number with ordinal indicator (Ex: 17th)
            '''
            if int(num) in range(11, 20): # If a 'teen' number. (11, 12, 13, ...)
                return f"{int(num)}th"
            elif str(num)[-1] == "1": # If number ends in "1"
                return f"{int(num)}st"
            elif str(num)[-1] == "2": # If number ends in "2"
                return f"{int(num)}nd"
            elif str(num)[-1] == "3": # If number ends in "3"
                return f"{int(num)}rd"
            else:
                return f"{int(num)}th"

    def promoCitation(self):
        # Make promotion citation.
        rankShort = self.requestedRank["short"]

        img = Image.open(f"templates/{rankShort}.jpeg")
        draw = ImageDraw.Draw(img)

        def writeText(confName, text):
            nonlocal img, draw
            c = self.requestedRank["citation"][confName]
            x, y = c["pos"]
            font = ImageFont.truetype(c["fontName"], c["fontSize"])
            
            w, h = draw.textsize(text, font=font)
            draw.text(
                (x-(w/2), y-(h/2)), 
                text, 
                (0,0,0), 
                font=font
            )

        # Write name
        writeText("name", self.trooper["real_name"].upper())
        
        # Handle dateText formating
        dt = datetime.strptime(self.date, "%d-%b-%Y")
        dateReplace = [
            ["[d]", self.ordinalIndicator(dt.strftime("%d"))],
            ["[D]", self.ordinalIndicator(dt.strftime("%d")).upper()],
            ["[m]", dt.strftime("%B")],
            ["[M]", dt.strftime("%B").upper()],
            ["[y]", dt.strftime("%Y")]
        ]
        dateText = self.requestedRank["citation"]["date"]["dateText"]
        for r in dateReplace:
            dateText = dateText.replace(r[0], r[1])
        
        # Write date
        writeText("date", dateText)

        # Save the file
        try:
            os.makedirs(f"generatedCitations/{self.folderName()}")
        except:
            pass

        fileName = f"generatedCitations/{self.folderName()}/"+self.requestedRank["paygrade"]+"-"+self.requestedRank["short"]+"-"+dt.strftime("%y%m%d")+".jpeg"
        img.save(fileName)

        print(f"{fileName} Generated")

    def ncoCitation(self):
        # Make NCO ribbon citation. if Required

        # If NCO ribbon not required, terminate function.
        if self.requestedRank["NCORibbon"] == False:
            return False

        rawAwards = requests.get(
            f"https://api.7cav.us/v1/user/{self.userID}/awards",
            headers={"Authorization": f"Bearer {self.APIKey}"}
        ).json()["data"]
        fullRank = self.requestedRank["long"]

        # If the trooper already has NCO ribbon, temrinate function.
        if any(i for i in rawAwards if f"{fullRank} Promotion" in i["details"]):
            return False

        # Make NCO Ribbon citation.
        rankShort = self.requestedRank["short"]
        img = Image.open(f"templates/NCO-{rankShort}.jpeg")
        draw = ImageDraw.Draw(img)

        def writeText(confName, text):
            nonlocal img, draw
            c = self.config["NCORibbon"]["citation"][confName]
            x, y = c["pos"]
            font = ImageFont.truetype(c["fontName"], c["fontSize"])
            
            w, h = draw.textsize(text, font=font)
            draw.text(
                (x-(w/2), y-(h/2)), 
                text, 
                (0,0,0), 
                font=font
            )

        # Write name
        citationName = self.requestedRank["long"]+" "+self.trooper["real_name"]
        writeText("name", citationName.upper())
        
        # Handle dateText formating
        dt = datetime.strptime(self.date, "%d-%b-%Y")
        dateReplace = [
            ["[d]", self.ordinalIndicator(dt.strftime("%d"))],
            ["[D]", self.ordinalIndicator(dt.strftime("%d")).upper()],
            ["[m]", dt.strftime("%B")],
            ["[M]", dt.strftime("%B").upper()],
            ["[y]", dt.strftime("%Y")]
        ]
        dateText = self.config["NCORibbon"]["citation"]["date"]["dateText"]
        for r in dateReplace:
            dateText = dateText.replace(r[0], r[1])
        
        # Write date
        writeText("date", dateText)

        # Save the file
        fileName = f"generatedCitations/{self.folderName()}/NCO-"+self.requestedRank["short"]+"-"+dt.strftime("%y%m%d")+".jpeg"
        img.save(fileName)

        print(f"{fileName} Generated")
    
    def forumPost(self):
        # Generate forum post
        pass

if __name__ == "__main__":
    promotion(
        milpacID=258,
        rank="SGT",
        date="17-Mar-2020"
    ).push()
