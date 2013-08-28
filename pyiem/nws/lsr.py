import re
import datetime
import pytz

from pyiem import reference

MAG_UNITS = re.compile(r"(ACRE|INCHES|INCH|MILE|MPH|KTS|U|FT|F|E|M|TRACE)")

class LSR(object):
    ''' Represents a single Local Storm Report within the LSRProduct '''

    def __init__(self):
        ''' constructor '''
        self.utcvalid = None
        self.valid = None
        self.typetext = None
        self.geometry = None
        self.city = None
        self.county = None
        self.source = None
        self.remark = None
        self.magnitude_f = None
        self.magnitude_str = None
        self.magnitude_qualifier = None
        self.magnitude_units = None
        self.state = None
        self.source = None
        self.text = None
        self.wfo = None
    
    def get_lat(self):
        return self.geometry.xy[1][0]
    
    def get_lon(self):
        return self.geometry.xy[0][0]
                
    def consume_magnitude(self, text):
        ''' Convert LSR magnitude text into something atomic '''
        self.magnitude_str = text
        tokens = MAG_UNITS.findall(text)
        if len(tokens) == 2:
            self.magnitude_qualifier = tokens[0]
            self.magnitude_units = tokens[1]
        elif len(tokens) == 1:
            self.magnitude_units = tokens[0]
        val = MAG_UNITS.sub('', text).strip()
        if val != '':
            self.magnitude_f = float(val)

    def sql(self, txn):
        ''' Provided a database transaction object, persist this LSR '''
        table = "lsrs_%s" % (self.utcvalid.year,)
        wkt = "SRID=4326;%s" % (self.geometry.wkt,)
        sql = """INSERT into """+table +""" (valid, type, magnitude, city, 
               county, state, source, remark, geom, wfo, typetext) 
               values (%s, %s, %s, %s, %s, %s, 
               %s, %s, %s, %s, %s)"""
        args = (self.utcvalid, 
                reference.lsr_events.get(self.typetext, None),
                self.magnitude_f, self.city, self.county, self.state,
                self.source, self.remark, wkt, self.wfo, self.typetext)
        txn.execute(sql, args)

    def tweet(self):
        ''' return a tweet text '''
        msg = 'At %s, %s reports %s #%s' % (self.valid.strftime('%-I:%M %p'),
                                        self.source, self.mag_string(),
                                        self.wfo)
        return msg
        
    def get_jabbers(self, uri='http://localhost'):
        ''' return a plain text and html string representing this LSR '''
        time_fmt = "%-I:%M %p %Z"
        now = datetime.datetime.utcnow()
        now = now.replace(tzinfo=pytz.timezone("UTC")) - datetime.timedelta(
                                                                    hours=24)
        if self.valid < now:
            time_fmt = "%-d %b, %-I:%M %p %Z"

        html = "%s [%s Co, %s] %s <a href=\"%s\">reports %s</a> at %s -- %s" % (
            self.city, self.county, self.state, self.source,
              uri, self.mag_string(),
              self.valid.strftime(time_fmt), self.remark)
        
        plain = "%s [%s Co, %s] %s reports %s at %s -- %s %s" % (
            self.city, self.county, self.state, self.source,
              self.mag_string(),
              self.valid.strftime(time_fmt), self.remark, uri)
        
        return plain, html
        
    def assign_timezone(self, tz, z):
        ''' retroactive assignment of timezone, so to improve attrs '''
        if self.valid is None:
            return
        # We can't just assign the timezone as this does not work in pytz
        self.utcvalid = self.valid + datetime.timedelta(
                                                hours= reference.offsets[z] )
        self.utcvalid = self.utcvalid.replace(tzinfo=pytz.timezone("UTC"))
        self.valid = self.utcvalid.astimezone(tz)
        
    def mag_string(self):
        ''' Return a string representing the magnitude and units '''
        mag_long = "%s" % (self.typetext,)
        if (self.typetext == "HAIL" and 
            reference.hailsize.has_key("%.2f" % (self.magnitude_f,))):
            haildesc = reference.hailsize["%.2f" % (self.magnitude_f,)]
            mag_long = "%s of %s size (%s%.2f %s)" % (mag_long,
                                                      haildesc, 
                                                      self.magnitude_qualifier,
                                                      self.magnitude_f,
                                                      self.magnitude_units)
        elif self.magnitude_f:
            mag_long = "%s of %.2f %s" % (mag_long, self.magnitude_f, 
                                        self.magnitude_units)
        elif self.magnitude_str:
            mag_long = "%s of %s" % (mag_long, self.magnitude_str)
        return mag_long