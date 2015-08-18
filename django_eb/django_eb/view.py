from django.http import HttpResponse
from django.http import JsonResponse
import datetime
import json

import sys
sys.path.append("/opt/python2.7-selected-site-packages/numpy")
import numpy

sys.path.append("/opt/python2.7-selected-site-packages/pgmagick")
import pgmagick as pg

sys.path.append("/opt/python2.7-selected-site-packages/pil")
import PIL
from PIL import Image

from collections import namedtuple
import random
from math import sqrt

Point = namedtuple('Point', ('coords', 'n', 'ct'))
Cluster = namedtuple('Cluster', ('points', 'center', 'n'))

def now(request):
	print 'Raw Data: "%s"' % request.body
	now = datetime.datetime.now()
	html = "<html><body>It is now %s.</body></html>" % now
	return HttpResponse(html)

def trans_mask_sobel(img):
    """ Generate a transparency mask for a given image """

    image = pg.Image(str(img))

    # Find object
    image.negate()
    image.edge()
    image.blur(1)
    image.threshold(24)
    image.adaptiveThreshold(5, 5, 5)

    # Fill background
    image.fillColor('magenta')
    w, h = image.size().width(), image.size().height()
    image.floodFillColor('0x0', 'magenta')
    image.floodFillColor('0x0+%s+0' % (w-1), 'magenta')
    image.floodFillColor('0x0+0+%s' % (h-1), 'magenta')
    image.floodFillColor('0x0+%s+%s' % (w-1, h-1), 'magenta')

    image.transparent('magenta')
    return image

def alpha_composite(image, mask):
    """ Composite two images together by overriding one opacity channel """

    compos = pg.Image(str(mask))
    compos.composite(
        image,
        image.size(),
        pg.CompositeOperator.CopyOpacityCompositeOp
    )
    return compos

def get_points(img):
    #Point = namedtuple('Point', ('coords', 'n', 'ct'))
    points = []
    w, h = img.size
    for count, color in img.getcolors(w * h):
        points.append(Point(color, 3, count))
    return points

rtoh = lambda rgb: '#%s' % ''.join(('%02x' % p for p in rgb))

def euclidean(p1, p2):
    return sqrt(sum([
        (p1.coords[i] - p2.coords[i]) ** 2 for i in range(p1.n)
    ]))

def calculate_center(points, n):
    #Point = namedtuple('Point', ('coords', 'n', 'ct'))
    vals = [0.0 for i in range(n)]
    plen = 0
    for p in points:
        plen += p.ct
        for i in range(n):
            vals[i] += (p.coords[i] * p.ct)
    return Point([(v / plen) for v in vals], n, 1)

def kmeans(points, k, min_diff):
    clusters = [Cluster([p], p, p.n) for p in random.sample(points, k)]

    while 1:
        plists = [[] for i in range(k)]

        for p in points:
            smallest_distance = float('Inf')
            for i in range(k):
                distance = euclidean(p, clusters[i].center)
                if distance < smallest_distance:
                    smallest_distance = distance
                    idx = i
            plists[idx].append(p)

        diff = 0
        for i in range(k):
            old = clusters[i]
            center = calculate_center(plists[i], old.n)
            new = Cluster(plists[i], center, old.n)
            clusters[i] = new
            diff = max(diff, euclidean(old.center, new.center))

        if diff < min_diff:
            break

    return clusters

def colorz(imgfile, n=3):
    #blob_reader = blobstore.BlobReader(blob_key)
    img = Image.open(imgfile)
    w, h = img.size
    print 'img w: "%s"' % str(w)
    print 'img h: "%s"' % str(h)
    img.thumbnail((200, 200))

    points = get_points(img)
    #print 'point: "%s"' % str(points)
    clusters = kmeans(points, n, 1)
    #print 'clusters: "%s"' % str(clusters)
    rgbs = [map(int, c.center.coords) for c in clusters]
    #print 'rgbs: "%s"' % str(rgbs)
    return map(rtoh, rgbs)

def remove_background(request):
    """ Remove the background of the image in 'filename' """

    print 'Raw Data: "%s"' % request.body
    print 'extracting json'

    received_json_data = json.loads(request.body)
    print 'json: "%s"' % received_json_data

    img = received_json_data['imageurl']
    print 'Image File: "%s"' % img

    transmask = trans_mask_sobel(img)
    img = alpha_composite(transmask, img)
    img.trim()
    img.write('out.png')

    # get hexcolors after removing the background
    hexcolors = colorz('out.png')
    print 'hexcolors: "%s"' % str(hexcolors)

    response_data = {'colors':hexcolors}
    #response_data = {}
    #response_data ['colors'] = hexcolors

    return JsonResponse(response_data, safe=False)