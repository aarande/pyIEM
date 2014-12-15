"""
Parser for NWS Climate Report text format
"""
import re
import datetime

from pyiem.nws.product import TextProduct

HEADLINE_RE = re.compile(r"\.\.\.THE ([A-Z_\.\-\(\)\/\,\s]+) CLIMATE SUMMARY FOR\s+([A-Z]+\s[0-9]+\s+[0-9]{4})( CORRECTION)?\.\.\.")

class CLIException(Exception):
    """ Exception """
    pass

def trace(val):
    """ This value could be T or M, account for it! """
    if val == 'M' or val == 'MM':
        return None
    if val == 'T':
        return 0.0001
    return float(val)

def trace_r(val):
    """ Convert our value back into meaningful string """
    if val == 0.0001:
        return 'Trace'
    return val

def get_number(s):
    """ Convert a string into a number, preferable a float! """
    s = s.strip()
    if s == '':
        return None
    if s == 'MM':
        return None
    if s == 'T':
        return 0.0001
    number = re.findall("[-+]?\d*\.\d+|\d+", s)
    if len(number) == 1:
        if s.find("."):
            return float(number[0])
        else:
            return int(number[0])
    print 'get_number() failed for |%s|' % (s,)
    return None

def convert_key(s):
    """ Convert a key value to something we store """
    if s == 'YESTERDAY':
        return 'today'
    if s == 'TODAY':
        return 'today'
    if s == 'MONTH TO DATE':
        return 'month'
    if s.startswith('SINCE '):
        return s.replace('SINCE ', '').replace(' ', "").lower()
    print 'convert_key() failed for |%s|' % (s,)
    return 'fail'

def parse_snowfall(lines, data):
    """ Parse the snowfall data 
WEATHER ITEM   OBSERVED TIME   RECORD YEAR NORMAL DEPARTURE LAST
                VALUE   (LST)  VALUE       VALUE  FROM      YEAR 
                                                  NORMAL
SNOWFALL (IN)
  YESTERDAY        0.0          MM      MM   0.0    0.0      0.0
  MONTH TO DATE    0.0                       0.0    0.0      0.0
  SINCE JUN 1      0.0                       0.0    0.0      0.0
  SINCE JUL 1      0.0                       0.0    0.0      0.0
  SNOW DEPTH       0
    """
    for linenum, line in enumerate(lines):
        # Replace trace with IEM internal storage of 0.0001
        numbers = re.findall("[-+]?\d*\.\d+|\d+| T ", line)
        if len(numbers) == 0:
            continue
        # Spaces are stripped by this point
        line = "%-70s" % (line,)
        # skipme
        if len(line.strip()) < 14:
            continue
        key = line[:14].strip()
        if key == 'SNOW DEPTH':
            continue
        key = convert_key(key)
        data['snow_%s' % (key,)] = get_number(line[15:21])
        data['snow_%s_record' % (key,)] = get_number(line[29:35])
        yeartest = get_number(line[36:40])
        if yeartest is not None:
            data['snow_%s_record_years' % (key,)] = [yeartest,]
        data['snow_%s_normal' % (key,)] = get_number(line[41:47])
        data['snow_%s_departure' % (key,)] = get_number(line[48:54])
        data['snow_%s_last' % (key,)] = get_number(line[57:63])
        if (key == 'today' and yeartest is not None and
            data['snow_%s_record_years' % (key,)][0] is not None):
                while ((linenum+1)<len(lines) and 
                       len(lines[linenum+1].strip()) == 4):
                    data['snow_today_record_years'].append(
                                                    int(lines[linenum+1]))
                    linenum += 1

def parse_precipitation(lines, data):
    """ Parse the precipitation data """
    for linenum, line in enumerate(lines):
        # careful here as if T is only value, the trailing space is stripped
        line = (line+" ").replace(" T ", "0.0001")
        numbers = re.findall("[-+]?\d*\.\d+|\d+", line)
        if line.startswith("YESTERDAY") or line.startswith("TODAY"):
            if len(numbers) == 0:
                continue
            data['precip_today'] = float(numbers[0])
            if len(numbers) == 6:
                data['precip_today_normal'] = float(numbers[3])
                data['precip_today_record'] = float(numbers[1])
                data['precip_today_record_years'] = [int(numbers[2]),]
                # Check next line(s) for more years
                while ((linenum+1)<len(lines) and 
                       len(lines[linenum+1].strip()) == 4):
                    data['precip_today_record_years'].append(
                                                    int(lines[linenum+1]))
                    linenum += 1
        elif line.startswith("MONTH TO DATE"):
            data['precip_month'] = float(numbers[0])
            if len(numbers) == 4:
                data['precip_month_normal'] = float(numbers[1])
        elif line.startswith("SINCE JAN 1"):
            data['precip_jan1'] = float(numbers[1])
            if len(numbers) == 4:
                data['precip_jan1_normal'] = float(numbers[2])
        elif line.startswith("SINCE JUL 1"):
            data['precip_jul1'] = float(numbers[1])
            if len(numbers) == 4:
                data['precip_jul1_normal'] = float(numbers[2])
        elif line.startswith("SINCE JUN 1"):
            data['precip_jun1'] = float(numbers[1])
            if len(numbers) == 4:
                data['precip_jun1_normal'] = float(numbers[2])
        elif line.startswith("SINCE DEC 1"):
            data['precip_dec1'] = float(numbers[1])
            if len(numbers) == 4:
                data['precip_dec1_normal'] = float(numbers[2])

def no99(val):
    """ Giveme int val of null! """
    if val == '-99':
        return None
    return int(val)

def parse_temperature(lines, data):
    """ Here we parse a temperature section
WEATHER ITEM   OBSERVED TIME   RECORD YEAR NORMAL DEPARTURE LAST
                VALUE   (LST)  VALUE       VALUE  FROM      YEAR
                                                  NORMAL
..................................................................
TEMPERATURE (F)
 YESTERDAY
  MAXIMUM         89    309 PM 101    1987  85      4       99
  MINIMUM         63    545 AM  51    1898  67     -4       69
  AVERAGE         76                        76      0       84
    """
    for linenum, line in enumerate(lines):
        numbers = re.findall("\-?\d+", line.replace(" MM ", " -99 "))
        if line.startswith("MAXIMUM"):
            data['temperature_maximum'] = no99(numbers[0])
            tokens = re.findall("([0-9]{3,4} [AP]M)", line)
            if len(tokens) == 1:
                data['temperature_maximum_time'] = tokens[0]
            if len(numbers) == 7: # we know this
                data['temperature_maximum_record'] = no99(numbers[2])
                if int(numbers[3]) > 0:
                    data['temperature_maximum_record_years'] = [int(numbers[3]),]
                data['temperature_maximum_normal'] = no99(numbers[4])
                # Check next line(s) for more years
                while ((linenum+1)<len(lines) and 
                       len(lines[linenum+1].strip()) == 4):
                    data['temperature_maximum_record_years'].append(
                                                    int(lines[linenum+1]))
                    linenum += 1
        if line.startswith("MINIMUM"):
            data['temperature_minimum'] = no99(numbers[0])
            tokens = re.findall("([0-9]{3,4} [AP]M)", line)
            if len(tokens) == 1:
                data['temperature_minimum_time'] = tokens[0]
            if len(numbers) == 7: # we know this
                data['temperature_minimum_record'] = no99(numbers[2])
                if int(numbers[3]) > 0:
                    data['temperature_minimum_record_years'] = [int(numbers[3]),]
                data['temperature_minimum_normal'] = no99(numbers[4])
                while ((linenum+1)<len(lines) and 
                       len(lines[linenum+1].strip()) == 4):
                    data['temperature_minimum_record_years'].append(
                                                    int(lines[linenum+1]))
                    linenum += 1

class CLIProduct(TextProduct):
    """
    Represents a CLI Daily Climate Report Product
    """

    def __init__(self, text):
        """ constructor """
        TextProduct.__init__(self, text)
        # Hold our parsing results as an array of dicts
        self.data = []
        if self.wmo[:2] != 'CD':
            print 'Product %s skipped due to wrong header' % (
                                                    self.get_product_id(),)
            return
        for section in self.unixtext.split("&&"):
            if len(HEADLINE_RE.findall(section.replace("\n", " "))) == 0:
                continue
            # We have meat!
            valid, station = self.parse_cli_headline(section)
            data = self.parse_data(section)
            self.data.append(dict(cli_valid=valid,
                                  cli_station=station,
                                  data=data))

    def get_jabbers(self, uri, _=None):
        """ Override the jabber message formatter """
        url = "%s?pid=%s" % (uri, self.get_product_id())
        res = []
        for data in self.data:
            mess = "%s %s Climate Report: High: %s Low: %s Precip: %s Snow: %s %s" % (
                        data['cli_station'], 
                        data['cli_valid'].strftime("%b %-d"),
                        data['data'].get('temperature_maximum', 'M'),
                        data['data'].get('temperature_minimum', 'M'),
                        trace_r(data['data'].get('precip_today', 'M')),
                        trace_r(data['data'].get('snow_today', 'M')), url
                        )
            htmlmess = ("%s <a href=\"%s\">%s Climate Report</a>: High: %s "
                        +"Low: %s Precip: %s Snow: %s") % (
                        data['cli_station'], url, data['cli_valid'].strftime("%b %-d"),
                        data['data'].get('temperature_maximum', 'M'),
                        data['data'].get('temperature_minimum', 'M'),
                        trace_r(data['data'].get('precip_today', 'M')),
                        trace_r(data['data'].get('snow_today', 'M'))
                        )
            tweet = "%s %s Climate: Hi: %s Lo: %s Precip: %s Snow: %s %s" % (
                        data['cli_station'], data['cli_valid'].strftime("%b %-d"),
                        data['data'].get('temperature_maximum', 'M'),
                        data['data'].get('temperature_minimum', 'M'),
                        trace_r(data['data'].get('precip_today', 'M')),
                        trace_r(data['data'].get('snow_today', 'M')), url
                        )
            res.append([mess.replace("0.0001", "Trace"), 
                        htmlmess.replace("0.0001", "Trace"), {
                            'channels': self.afos,
                            'twitter': tweet
                    }])
        return res

    def parse_data(self, section):
        """ Actually do the parsing of this silly format """
        data = {}
        pos = section.find("TEMPERATURE")
        if pos == -1:
            raise CLIException('Failed to find TEMPERATURE, aborting')

        # Strip extraneous spaces
        meat = "\n".join([l.strip() for l in section[pos:].split("\n")])
        # Don't look into aux data for things we should not be parsing
        if meat.find("&&") > 0:
            meat = meat[:meat.find("&&")]
        sections = meat.split("\n\n")
        for section in sections:
            lines = section.split("\n")
            if lines[0] in ["TEMPERATURE (F)", 'TEMPERATURE']:
                parse_temperature(lines, data)
            elif lines[0] in ['PRECIPITATION (IN)', 'PRECIPITATION']:
                parse_precipitation(lines, data)
            elif lines[0] in ['SNOWFALL (IN)', 'SNOWFALL']:
                parse_snowfall(lines, data)

        return data

    def parse_cli_headline(self, section):
        """ Figure out when this product is valid for """
        tokens = HEADLINE_RE.findall( section.replace("\n", " ") )
        if len(tokens) == 1:
            if len(tokens[0][1].split()[0]) == 3:
                myfmt = '%b %d %Y'
            else:
                myfmt = '%B %d %Y'
            cli_valid = datetime.datetime.strptime(tokens[0][1], myfmt)
            cli_station = (tokens[0][0]).strip()
            return cli_valid, cli_station  
        elif len(tokens) > 1:
            raise CLIException("Found two headers in product, unsupported!")
        else:
            # Known sources of bad data...
            if self.source in ['PKMR', 'NSTU', 'PTTP', 'PTKK', 'PTKR']:
                return None
            raise CLIException('Could not find date valid in %s' % (
                                                self.get_product_id(),))

def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ Provide back CLI objects based on the parsing of this text """
    # Careful here, see if we have two CLIs in one product!
    return CLIProduct( text )
