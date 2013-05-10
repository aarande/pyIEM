"""
  OO interface to properly generate fancy pants IEM plots

Like it or not, we care about zorder!

  z
  1 Continent fill
  2 contour or fill
  3 polygon clipping
  4 states
  5 overlay text
"""
[Z_CF, Z_FILL, Z_CLIP, Z_POLITICAL, Z_OVERLAY] = range(1,6)

import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
from matplotlib.colors import rgb2hex
from matplotlib.patches import Polygon
import matplotlib.cm as cm
import matplotlib.colors as mpcolors
import matplotlib.patheffects as PathEffects
import mx.DateTime
import numpy
from scipy.interpolate import griddata
from pyiem import reference
import Image
import cStringIO
import tempfile
import os
import sys
import subprocess
import shutil

DATADIR = os.sep.join([os.path.dirname(__file__), 'data'])

from matplotlib.artist import Artist

def smooth1d(x, window_len):
    # copied from http://www.scipy.org/Cookbook/SignalSmooth

    s=numpy.r_[2*x[0]-x[window_len:1:-1],x,2*x[-1]-x[-1:-window_len:-1]]
    w = numpy.hanning(window_len)
    y=numpy.convolve(w/w.sum(),s,mode='same')
    return y[window_len-1:-window_len+1]

def smooth2d(A, sigma=3):

    window_len = max(int(sigma), 3)*2+1
    A1 = numpy.array([smooth1d(x, window_len) for x in numpy.asarray(A)])
    A2 = numpy.transpose(A1)
    A3 = numpy.array([smooth1d(x, window_len) for x in A2])
    A4 = numpy.transpose(A3)

    return A4

class BaseFilter(object):
    def prepare_image(self, src_image, dpi, pad):
        ny, nx, depth = src_image.shape
        #tgt_image = numpy.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src = numpy.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src[pad:-pad, pad:-pad,:] = src_image[:,:,:]

        return padded_src#, tgt_image

    def get_pad(self, dpi):
        return 0

    def __call__(self, im, dpi):
        pad = self.get_pad(dpi)
        padded_src = self.prepare_image(im, dpi, pad)
        tgt_image = self.process_image(padded_src, dpi)
        return tgt_image, -pad, -pad

class GrowFilter(BaseFilter):
    "enlarge the area"
    def __init__(self, pixels, color=None):
        self.pixels = pixels
        if color is None:
            self.color=(1, 1, 1)
        else:
            self.color=color

    def __call__(self, im, dpi):
        pad = self.pixels
        ny, nx, depth = im.shape
        new_im = numpy.empty([pad*2+ny, pad*2+nx, depth], dtype="d")
        alpha = new_im[:,:,3]
        alpha.fill(0)
        alpha[pad:-pad, pad:-pad] = im[:,:,-1]
        alpha2 = numpy.clip(smooth2d(alpha, self.pixels/72.*dpi) * 5, 0, 1)
        new_im[:,:,-1] = alpha2
        new_im[:,:,:-1] = self.color
        offsetx, offsety = -pad, -pad

        return new_im, offsetx, offsety

class FilteredArtistList(Artist):
    """
    A simple container to draw filtered artist.
    """
    def __init__(self, artist_list, _filter):
        self._artist_list = artist_list
        self._filter = _filter
        Artist.__init__(self)

    def draw(self, renderer):
        renderer.start_rasterizing()
        renderer.start_filter()
        for a in self._artist_list:
            a.draw(renderer)
        renderer.stop_filter(self._filter)
        renderer.stop_rasterizing()

def load_bounds(filename):
    """
    Load the boundary file into a [numpy array]
    """
    res = []
    # line for x, line for y, repeat...
    is_x = True
    for line in open("%s/%s" % (DATADIR, filename), 'r'):
        tokens = line.split(",")
        arr = []
        for token in tokens:
            arr.append( float(token) )
        pos = 1
        if is_x:
            res.append( numpy.zeros((len(tokens),2), 'f') )
            pos = 0
            is_x = False
    
        res[-1][:,pos] = arr
    
    return res

def mask_outside_polygon(poly_verts, ax=None):
    """
    Plots a mask on the specified axis ("ax", defaults to plt.gca()) such
that
    all areas outside of the polygon specified by "poly_verts" are masked.

    "poly_verts" must be a list of tuples of the verticies in the polygon in
    counter-clockwise order.

    Returns the matplotlib.patches.PathPatch instance plotted on the figure.
    """
    import matplotlib.patches as mpatches
    import matplotlib.path as mpath

    if ax is None:
        ax = plt.gca()

    # Get current plot limits
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    # Verticies of the plot boundaries in clockwise order
    bound_verts = [(xlim[0], ylim[0]), (xlim[0], ylim[1]),
                   (xlim[1], ylim[1]), (xlim[1], ylim[0]),
                   (xlim[0], ylim[0])]

    # A series of codes (1 and 2) to tell matplotlib whether to draw a lineor
    # move the "pen" (So that there's no connecting line)
    bound_codes = [mpath.Path.MOVETO] + (len(bound_verts) - 1) *[mpath.Path.LINETO]
    poly_codes = [mpath.Path.MOVETO] + (len(poly_verts) - 1) *[mpath.Path.LINETO]

    # Plot the masking patch
    path = mpath.Path(bound_verts + poly_verts, bound_codes + poly_codes)
    patch = mpatches.PathPatch(path, facecolor='white', edgecolor='none', 
                               zorder=Z_CLIP)
    patch = ax.add_patch(patch)

    # Reset the plot limits to their original extents
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    return patch

def maue(N=-1):
    """ Pretty color ramp Dr Ryan Maue uses """
    cpool = ["#e6e6e6", "#d2d2d2", "#bcbcbc", "#969696", "#646464",
"#1464d2", "#1e6eeb", "#2882f0", "#3c96f5", "#50a5f5", "#78b9fa", 
           "#96d2fa", "#b4f0fa", "#e1ffff",
"#0fa00f", "#1eb41e", "#37d23c", "#50f050", "#78f573", "#96f58c", 
           "#b4faaa", "#c8ffbe",
"#ffe878", "#ffc03c", "#ffa000", "#ff6000", "#ff3200", "#e11400", "#c00000", 
           "#a50000", "#643c32",
"#785046", "#8c645a", "#b48c82", "#e1beb4", "#f0dcd2", "#ffc8c8", "#f5a0a0", 
           "#f5a0a0", "#e16464", "#c83c3c"]
    if N == 15:
        cpool = cpool[::2]
    #cmap3 = mpcolors.ListedColormap(cpool[0:N], 'maue', N=N)
    cmap3 = mpcolors.ListedColormap(cpool, 'maue')
    cm.register_cmap(cmap=cmap3)
    return cmap3

def LevelColormap(levels, cmap=None):
    """Make a colormap based on an increasing sequence of levels"""
    
    # Start with an existing colormap
    #if cmap == None:
    #    cmap = pl.get_cmap()

    # Spread the colours maximally
    nlev = len(levels)
    S = numpy.arange(nlev, dtype='float')/(nlev-1)
    A = cmap(S)

    # Normalize the levels to interval [0,1]
    levels = numpy.array(levels, dtype='float')
    L = (levels-levels[0])/(levels[-1]-levels[0])

    # Make the colour dictionary
    R = [(L[i], A[i,0], A[i,0]) for i in xrange(nlev)]
    G = [(L[i], A[i,1], A[i,1]) for i in xrange(nlev)]
    B = [(L[i], A[i,2], A[i,2]) for i in xrange(nlev)]
    cdict = dict(red=tuple(R),green=tuple(G),blue=tuple(B))

    # Use 
    return mpcolors.LinearSegmentedColormap(
        '%s_levels' % cmap.name, cdict, 256)

class MapPlot:
    
    def __init__(self, sector='iowa', figsize=(10.24,7.68), **kwargs):
        """ Initializer """
        self.fig = plt.figure(num=None, figsize=figsize )
        self.fig.subplots_adjust(bottom=0, left=0, right=1, top=1, wspace=0, 
                                 hspace=0)
        self.ax = plt.axes([0.01,0.05,0.9,0.85], axisbg=(0.4471,0.6235,0.8117))
        self.sector = sector
        if self.sector == 'iowa':
            """ Standard view for Iowa """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=reference.IA_NORTH, 
                           llcrnrlat=reference.IA_SOUTH, 
                           urcrnrlon=reference.IA_EAST, 
                           llcrnrlon=reference.IA_WEST, 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
        if self.sector == 'midwest':
            """ Standard view for Iowa """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=reference.MW_NORTH, 
                           llcrnrlat=reference.MW_SOUTH, 
                           urcrnrlon=reference.MW_EAST, 
                           llcrnrlon=reference.MW_WEST, 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
            self.map.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            self.map.drawcoastlines(zorder=Z_POLITICAL)
        elif self.sector == 'conus':
            # lat = 23.47693, 20.74123, 45.43908, 51.61555
            # lon = 118.6713, 82.3469, 64.52023, 131.4471 ;
            self.map = Basemap(projection='stere',lon_0=-105.0,lat_0=90.,
                            lat_ts=60.0,
                            llcrnrlat=23.47,urcrnrlat=45.44,
                            llcrnrlon=-118.67,urcrnrlon=-64.52,
                            rsphere=6371200.,resolution='l',area_thresh=10000,
                            ax=self.ax)
            self.map.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            self.map.drawcoastlines(zorder=Z_POLITICAL)
        self.map.fillcontinents(color='1.0', zorder=0) # Read docs on 0 meaning
        self.map.drawstates(linewidth=1.0, zorder=Z_OVERLAY, ax=self.ax)
        self.iemlogo()
        if kwargs.has_key("title"):
            self.fig.text(0.13, 0.94, kwargs.get("title"), fontsize=18) 
        if kwargs.has_key("subtitle"):
            self.fig.text(0.13, 0.91, kwargs.get("subtitle") )
        
        self.fig.text(0.01, 0.03, "Iowa Environmental Mesonet, generated %s" % (
                        mx.DateTime.now().strftime("%d %B %Y %I:%M %p %Z"),))
        
        self.pqstr = kwargs.get('pqstr', None)
        
        # Lazy and let a method below actually construct this
        self.colorbar = None

    def plot_values(self, lons, lats, vals, fmt='%s', valmask=None,
                    color='#000000'):
        """ Simply plot vals """        
        if valmask is None:
            valmask = [True] * len(lons)
        t = []
        for o,a,v,m in zip(lons, lats, vals, valmask):
            if m:
                x,y = self.map(o, a)
                t.append(self.ax.text(x, y, fmt % (v,) , color=color, 
                                      zorder=Z_OVERLAY))
                
        white_glows = FilteredArtistList(t, GrowFilter(3))
        self.ax.add_artist(white_glows)
        white_glows.set_zorder(t[0].get_zorder()-0.1)

    def contourf(self, lons, lats, vals, clevs, **kwargs):
        """ Contourf """
        if type(lons) == type([]):
            lons = numpy.array( lons )
            lats = numpy.array( lats )
            vals = numpy.array( vals )
        if vals.ndim == 1:
            # We need to grid!
            if self.sector == 'iowa':
                xi = numpy.linspace(reference.IA_WEST, reference.IA_EAST, 100)
                yi = numpy.linspace(reference.IA_SOUTH, reference.IA_NORTH, 100)
            else:
                xi = numpy.linspace(reference.MW_WEST, reference.MW_EAST, 100)
                yi = numpy.linspace(reference.MW_SOUTH, reference.MW_NORTH, 100)
            xi, yi = numpy.meshgrid(xi, yi)
            vals = griddata( zip(lons, lats), vals, (xi, yi) , 'cubic')
            lons = xi
            lats = yi
        if lons.ndim == 1:
            lons, lats = numpy.meshgrid(lons, lats)
        maue(len(clevs))

        cl = LevelColormap(clevs, cmap=cm.get_cmap('maue'))
        cl.set_under('#000000')
        
        x, y = self.map(lons, lats)
        cs = self.map.contourf(x, y, vals, clevs,
                               cmap=cl, zorder=Z_FILL)
        
        if self.sector == 'iowa':
            ia_border = load_bounds("iowa_bnds.txt")[0] # Only consider first
            xx,yy = self.map(ia_border[::-1,0], ia_border[::-1,1])            
            poly = zip(xx,yy)
            mask_outside_polygon(poly, ax=self.ax)
            
        cbar = self.map.colorbar(cs, location='right', pad="1%", 
                                 ticks=cs.levels)
        cbar.set_label( kwargs.get('units', ''))

    def fill_cwas(self, data,
                  shapefile='/mesonet/data/gis/static/shape/4326/nws/cwas',
                  bins=numpy.arange(0,100,10),
                  lblformat='%.0f'):
        """
        Added filled polygons to the plot based on key/value lookup pairs in
        the data dictionary
        """
        m = maue(15)
        self.map.readshapefile(shapefile, 'cwas', ax=self.ax)
        plotted = []
        for nshape, seg in enumerate(self.map.cwas):
            if not data.has_key(self.map.cwas_info[nshape]['CWA']):
                continue
            val = data.get( self.map.cwas_info[nshape]['CWA'] )
            idx = numpy.digitize([val],
                                 bins) 
            c = m( idx[0] - 1 )
            # Check area in meters... 100,000 x 100,000
            if self.map.cwas_info[nshape]['CWA'] not in plotted:
                mx, my = self.map(self.map.cwas_info[nshape]['LON'],
                                  self.map.cwas_info[nshape]['LAT'])
                txt = self.ax.text(mx, my, lblformat % (val,), zorder=100,
                         ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                         foreground="w")])
                plotted.append( self.map.cwas_info[nshape]['CWA'] )
            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            self.ax.add_patch(poly)

        if self.colorbar is None:
            # Yipeee, we get to build one!
            axaa = plt.axes([0.92, 0.1, 0.07, 0.8], frameon=False,
                      yticks=[], xticks=[])
            for i, mybin in enumerate(bins):
                txt = axaa.text(0.5, i, "%s" % (mybin,), ha='center', 
                                va='center', color='w')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2,
                                                     foreground="k")])

            axaa.barh(numpy.arange(len(bins)), [1]*len(bins), height=1,
                color=m(range(len(bins))),
                ec='None')


    def drawcounties(self):
        """ Draw counties """
        self.map.readshapefile('/mesonet/data/gis/static/shape/4326/iowa/iacounties', 'c')
        for nshape, seg in enumerate(self.map.c):
            poly=Polygon(seg, fill=False, ec='k', lw=.4, zorder=Z_POLITICAL)
            self.ax.add_patch(poly)

        
    def iemlogo(self):
        """ Draw a logo """
        logo = Image.open('/mesonet/www/apps/iemwebsite/htdocs/images/logo_small.png')
        ax3 = plt.axes([0.02,0.89,0.1,0.1], frameon=False, 
                       axisbg=(0.4471,0.6235,0.8117), yticks=[], xticks=[])
        ax3.imshow(logo, origin='upper')
        
    def make_colorbar(self, bins, colorramp):
        """ Manual Color Bar """
        ax = plt.axes([0.92, 0.1, 0.07, 0.8], frameon=False,
                      yticks=[], xticks=[])
        colors = []
        for i in range(len(bins)):
            colors.append( rgb2hex(colorramp(i)) )
            txt = ax.text(0.5, i, "%s" % (bins[i],), ha='center', va='center',
                          color='w')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                     foreground="k")])
        ax.barh(numpy.arange(len(bins)), [1]*len(bins), height=1,
                color=colorramp(range(len(bins))),
                ec='None')
        
    def postprocess(self, view=False, filename=None, web=False):
        """ postprocess into a slim and trim PNG """
        #if web:
        #    print "Content-Type: image/png\n"
        #    self.fig.savefig( sys.stdout, format='png' )
        #    return
        ram = cStringIO.StringIO()
        plt.savefig(ram, format='png')
        ram.seek(0)
        im = Image.open(ram)
        im2 = im.convert('RGB').convert('P', palette=Image.ADAPTIVE)
        if web:
            print "Content-Type: image/png\n"
            im2.save( sys.stdout, format='png' )
            return
        tmpfp = tempfile.mktemp()
        im2.save( tmpfp , format='PNG')
        
        if self.pqstr is not None:
            subprocess.call("/home/ldm/bin/pqinsert -p '%s' %s" % (self.pqstr, 
                                                                   tmpfp), 
                    shell=True)
        if view:
            subprocess.call("xv %s" % (tmpfp,), shell=True)
        if filename is not None:
            shutil.copyfile(tmpfp, filename)
        os.unlink(tmpfp)
        