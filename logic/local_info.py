# Obtain local information, such as long, lat, timezone, and elevation, using geopy and timezonefinder
# Also, obtain Sidereal Time using astropy and compute the Local Hour Angle of the Sun and the Galactic Center

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, SkyCoord, get_sun
import astropy.units as u
import datetime

def obtain_local_info():
    geolocator = Nominatim(user_agent="parttelescopes")
    location = geolocator.geocode("me")

    if location is None:
        print("Could not obtain location information.")
        return

    latitude = location.latitude
    longitude = location.longitude

    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=longitude, lat=latitude)

    if timezone_str is None:
        print("Could not determine timezone.")
        return

    local_time = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z%z')

    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_str,
        "local_time": local_time,
    }

def compute_sidereal_time_and_hour_angle(latitude, longitude):
    location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg)
    time = Time.now()
    sidereal_time = time.sidereal_time('mean', longitude=longitude * u.deg)

    sun = get_sun(time).transform_to(AltAz(obstime=time, location=location))
    galactic_center = SkyCoord(l=0 * u.deg, b=0 * u.deg, frame='galactic').transform_to(
        AltAz(obstime=time, location=location)
    )

    return {
        "sidereal_time": sidereal_time.to_string(unit='hour'),
        "sun_altitude": sun.alt.degree,
        "sun_azimuth": sun.az.degree,
        "galactic_center_altitude": galactic_center.alt.degree,
        "galactic_center_azimuth": galactic_center.az.degree,
    }