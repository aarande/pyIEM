# Class library for the NWN Baron format
#  OO is fun!
#  Daryl Herzmann 16 May 2003
# 18 Nov 2003    Fix a very stupid error in parseLineRT :(
#  5 Jan 2004    Forgot what a pleasure temperatures below zero are.  For 
#        whatever reason, the values from some KELO sites are reported
#        differently "0-5F".  This is not good
# 21 Oct 2004    Support wind averaging

# A 058  09:23 05/16/03 ESE 08MPH 050K 460F 057F 088% 30.02R 00.01"D 02.79"M 00.00"R
# H 025   Max  05/16/03 SE  08MPH 057K 460F 057F 100% 30.04" 00.00"D 03.55"M 00.00"R
# K 072   Min  05/16/03 NE  00MPH 000K 075F 048F 083% 30.02" 00.00"D 02.53"M 00.00"R

import datetime
import pytz
import re
import math
import pyiem.reference as reference
import traceback
import pyiem.util as util


def uv(sped, drct2):
    dirr = drct2 * math.pi / 180.00
    s = math.sin(dirr)
    c = math.cos(dirr)
    u = round(- sped * s, 2)
    v = round(- sped * c, 2)
    return u, v


def dwpf(tmpf, relh):
    """
    Compute the dewpoint in F given a temperature and relative humidity
    """
    if tmpf is None or relh is None:
        return None

    tmpk = 273.15 + ( 5.00/9.00 * ( tmpf - 32.00) )
    dwpk = tmpk / (1+ 0.000425 * tmpk * -(math.log10(relh/100.0)) )
    return int(float( ( dwpk - 273.15 ) * 9.00/5.00 + 32 ))


def mydir(u, v):
    if (v == 0):
        v = 0.000000001
    dd = math.atan(u / v)
    ddir = (dd * 180.00) / math.pi

    if (u > 0 and v > 0):
        ddir = 180 + ddir
    elif (u > 0 and v < 0):
        ddir = 360 + ddir
    elif (u < 0 and v < 0):
        ddir = ddir
    elif (u < 0 and v > 0):
        ddir = 180 + ddir

    return int(math.fabs(ddir))


def feelslike(tmpf, relh, sped):
    if (tmpf > 50):
        return heatidx(tmpf, relh)
    else:
        return wchtidx(tmpf, sped)


def heatidx(tmpf, relh):
    if tmpf < 70:
      return tmpf
    if (tmpf > 140):
      return -99
    if (relh == 0):
      return -99

    PR_HEAT =  61 + ( tmpf - 68 ) * 1.2 + relh * .094
    if (PR_HEAT < 77):
      return PR_HEAT

    t2 = tmpf * tmpf;
    t3 = tmpf * tmpf * tmpf
    r2 = relh * relh
    r3 = relh * relh * relh

    return (17.423 + 0.185212 * tmpf
            + 5.37941 * relh
            - 0.100254 * tmpf * relh
            +  0.00941695 * t2
            +  0.00728898 * r2
            +  0.000345372 * t2 * relh
            -  0.000814971 * tmpf * r2
            +  0.0000102102 * t2 * r2
            -  0.000038646 * t3
            +  0.0000291583 * r3
            +  0.00000142721 * t3 * relh
            +  0.000000197483 * tmpf * r3
            -  0.0000000218429 * t3 * r2
            +  0.000000000843296  * t2 * r3
            -  0.0000000000481975  * t3 * r3)


def wchtidx(tmpf, sped):
    if sped < 3 or tmpf > 50:
        return tmpf
    import math
    wci = math.pow(sped,0.16);

    return 35.74 + .6215 * tmpf - 35.75 * wci + .4275 * tmpf * wci


class nwnformat:

    def __init__(self, do_avg_winds=True):
        self.error = 0
        self.do_avg_winds = do_avg_winds

        self.sid = None
        self.ts = None
        self.avg_sknt = None
        self.avg_drct = None
        self.drct = None
        self.drctTxt = None
        self.avg_drctTxt = None
        self.sped = None
        self.rad = 0
        self.insideTemp = 460
        self.tmpf = None
        self.humid = None
        self.pres = None
        self.presTend = None
        self.pDay = 0.00
        self.pMonth = 0.00
        self.pRate = 0.00
        self.dwpf = None
        self.feel = None

        self.nhumid = 0
        self.xhumid = 0

        self.npres = 0
        self.xpres = 0

        self.xtmpf = None
        self.ntmpf = None
        self.xsped = None
        self.xdrct = None
        self.xdrctTxt = None
        self.xsrad = None

        self.strMaxLine = None
        self.strMinLine = None

        self.aSknt = []
        self.aDrct = []

    def avgWinds(self):
        if (len(self.aSknt) == 0):
            self.sped = None
            self.drct = None
            return

        self.avg_sknt = int(float(sum(self.aSknt)) / float(len(self.aSknt)))
        utot = 0
        vtot = 0
        for i in range(len(self.aSknt)):
            u, v = uv(self.aSknt[i], self.aDrct[i])
            if (self.aSknt[i] > self.xsped):
                self.xsped = self.aSknt[i] * 1.150
                self.xdrct = self.aDrct[i]
                self.xdrctTxt = util.drct2text(self.aDrct[i])

            utot += u
            vtot += v
        uavg = utot / len(self.aSknt)
        vavg = vtot / len(self.aSknt)
        self.avg_drct = mydir(uavg, vavg)
        self.avg_drctTxt = util.drct2text(self.avg_drct)

        self.aSknt = []
        self.aDrct = []

    def parseLineRT(self, tokens):
        if self.ts is None:
            _t = datetime.datetime.utcnow()
            _t = _t.replace(second=0, microsecond=0,
                            tzinfo=pytz.timezone("UTC"))
            self.ts = _t.astimezone(pytz.timezone("America/Chicago"))

        if (len(tokens) != 14):
            return
        lineType = tokens[2]
        if (lineType == "Max"):
            self.parseMaxLineRT(tokens)
        elif (lineType == "Min"):
            self.parseMinLineRT(tokens)
        else:
            _t = datetime.datetime.utcnow()
            _t = _t.replace(second=0, microsecond=0,
                            tzinfo=pytz.timezone("UTC"))
            self.ts = _t.astimezone(pytz.timezone("America/Chicago"))
            self.parseCurrentLineRT(tokens)

    def parseMaxLineRT(self, tokens):
        maxline = "found"
        self.xdrct = reference.txt2drct[tokens[4]]
        self.xdrctTxt = tokens[4]
        if (len(tokens[5]) >= 5):
            t = re.findall("([0-9]+)(MPH|KTS)", tokens[5])[0]
            if (t[1] == "MPH"):
                self.xsped = int(t[0])
            else:
                sknt = int(t[0])
                self.xsped = round( sknt * 1.1507, 0)

        if (len(tokens[6]) == 4):
            self.xsrad = int(re.findall("([0-9][0-9][0-9])[F,K]", tokens[6])[0]) * 10

        if (len(tokens[8]) == 4 or len(tokens[8]) == 3):
            if (tokens[8][0] == "0"):
                tokens[8] = tokens[8][1:] 
            self.xtmpf = int(tokens[8][:-1])

    def parseMinLineRT(self, tokens):
        if (len(tokens[8]) == 4 or len(tokens[8]) == 3):
            if (tokens[8][0] == "0"):
                tokens[8] = tokens[8][1:] 
            self.ntmpf = int(tokens[8][:-1])

    def parseCurrentLineRT(self, tokens):
        # ['M', '057', '09:57', '09/04/03', 'ESE', '01MPH', '058K', '460F', '065F', '070%', '30.34R', '00.00"D', '00.00"M', '00.00"R']
        # Don't forget about this lovely one!
        # ['M', '057', '09:57', '09/04/03', 'ESE', '01MPH', '058K', '460F', '0-5F', '070%', '30.34R', '00.00"D', '00.00"M', '00.00"R']
        if (len(tokens[8]) == 4 or len(tokens[8]) == 3):
            if (tokens[8][0] == "0"):
                tokens[8] = tokens[8][1:] 
            self.tmpf = int(tokens[8][:-1])

        self.drct = reference.txt2drct[tokens[4]]
        self.drctTxt = tokens[4]
        if (self.do_avg_winds):
            self.aDrct.append( int(self.drct) )

        if (len(tokens[5]) >= 5):
            t = re.findall("([0-9]+)(MPH|KTS)", tokens[5])[0]
            if (t[1] == "MPH"):
                self.sped = int(t[0])
                self.sknt = round( float(self.sped) *  0.868976, 0)
            else:
                self.sknt = int(t[0])
                self.sped = round( self.sknt / 0.868976, 0)
        if (self.do_avg_winds):
            self.aSknt.append(self.sknt)

        if (len(tokens[6]) == 4):
            self.rad = int(re.findall("([0-9][0-9][0-9])[F,K]", tokens[6])[0]) * 10

        if (len(tokens[9]) == 4):
            self.humid = int(re.findall("([0-9][0-9][0-9])%", tokens[9])[0]) 

        if (len(tokens[10]) == 6):
            self.pres = re.findall("(.*).", tokens[10])[0]

        if (len(tokens[11]) == 7):
            self.pDay = re.findall("(.*)\"D", tokens[11])[0]

        if (len(tokens[12]) == 7):
            self.pMonth = re.findall("(.*)\"M", tokens[12])[0]

        if (self.tmpf > -50 and self.tmpf < 120 and 
            self.humid > 5 and self.humid < 100.1):
            self.dwpf = dwpf(self.tmpf, self.humid)
            self.feel = feelslike(self.tmpf, self.humid, self.sped)
        else:
            self.dwpf = None
            self.feel = None

    def currentLine(self):
        try:
            return "%s %03i  %5s %8s %-3s %02iMPH %03iK %03iF %03iF %03i%s %05.2f%s %05.2f\"D %05.2f\"M %05.2f\"R\015\012" % ("A", self.sid, self.ts.strftime("%H:%M"), \
        self.ts.strftime("%m/%d/%y"), self.drctTxt, self.sped, self.rad, \
        self.insideTemp, self.tmpf, self.humid, "%", self.pres, self.presTend, self.pDay, self.pMonth, self.pRate)
        except:
            print "A", self.sid, self.ts.strftime("%H:%M"), \
        self.ts.strftime("%m/%d/%y"), self.drctTxt, self.sped, self.rad, \
        self.insideTemp, self.tmpf, self.humid, "%", self.pres, self.presTend, self.pDay, self.pMonth, self.pRate

    def maxLine(self):
        try:
            return "%s %03i  %5s %8s %-3s %02iMPH %03iK %03iF %03iF %03i%s %05.2f%s %05.2f\"D %05.2f\"M %05.2f\"R\015\012" % ("A", self.sid, "Max ", \
        self.ts.strftime("%m/%d/%y"), "N", self.xsped, self.rad, \
        self.insideTemp, self.xtmpf, self.xhumid, "%", self.xpres, self.presTend, 0, 0, 0)
        except:
            print "A", self.sid, "Max ", \
        self.ts.strftime("%m/%d/%y"), self.drctTxt, self.sped, self.rad, \
        self.insideTemp, self.xtmpf, self.xhumid, "%", self.xpres, self.presTend, self.pDay, self.pMonth, self.pRate
     

    def minLine(self):
        try:
            return "%s %03i  %5s %8s %-3s %02iMPH %03iK %03iF %03iF %03i%s %05.2f\" %05.2f\"D %05.2f\"M %05.2f\"R\015\012" % ("A", self.sid, "Min ", \
        self.ts.strftime("%m/%d/%y"), self.drctTxt, 0, 0, \
        self.insideTemp, self.ntmpf, self.nhumid, "%", self.npres, 0, 0, 0)
        except:
            print "A", self.sid, "Min ", \
        self.ts.strftime("%m/%d/%y"), self.drctTxt, 0, 0, \
        self.insideTemp, self.ntmpf, self.nhumid, "%", self.npres, 0, 0, 0
 

    def setPMonth(self, newval):
        if (newval != "NA"):
            self.pMonth = float(newval)

    def parseWind(self, newval):
        tokens = re.split("-", newval)
        if (len(tokens) != 2):
            return
  
        if (tokens[0] != "Missing"):
            self.drctTxt = tokens[0]
    
        if (tokens[1] == "Missing"):
            return
    
        try:
            self.sped = int(tokens[1])   
        except ValueError:
            traceback.print_exc()

    def setRad(self, newval):
        if (newval != "NA"):
            self.rad = newval

    def parsePDay(self, newval):
        if (newval == "Missing"):
            self.pDay = 0.00
        else:
            self.pDay = float(newval)

    # Make sure that nothing bad is going on here....
    def sanityCheck(self):
        if (self.xsped is None or self.xsped < 0):
            self.xsped = 0
            self.xdrct = -99

        if (self.pres is None or self.pres < 0):
            self.pres = 0
        if (self.pDay is None or self.pDay < 0):
            self.pDay = 0
        if (self.humid is None or self.humid < 0 or self.humid > 100):
            self.humid = 0
        if (self.tmpf == None or self.tmpf < -100 or self.tmpf > 150):
            self.tmpf = 460
        if (self.ntmpf == None or self.ntmpf < -100 or self.ntmpf > 150):
            self.ntmpf = 460
        if (self.xtmpf == None or self.xtmpf < -100 or self.xtmpf > 150):
            self.xtmpf = 460
        if (self.sped == None or self.sped < 0 or self.sped > 300):
            self.sped = 0
        if (self.avg_sknt == None or self.avg_sknt < 0 or self.avg_sknt > 300):
            self.avg_sknt = 0
        if (self.avg_drct == None or self.avg_drct < 0 or self.avg_drct > 360):
            self.avg_drct = 0
        if (self.xsrad == None or self.xsrad < 0 or self.xsrad > 10000):
            self.xsrad = 0