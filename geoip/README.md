# GeoIP data (not included in repository)

SecBoard uses MaxMind GeoLite2 City database for optional geolocation features.

## Setup

1. Create a free account at https://www.maxmind.com/en/geolite2/signup
2. Download **GeoLite2 City** in MaxMind DB (`.mmdb`) format
3. Place the file here:

```
geoip/GeoLite2-City.mmdb
```

## License

GeoLite2 data is subject to the [MaxMind GeoLite2 End User License Agreement](https://www.maxmind.com/en/geolite2/eula).
Do not commit `.mmdb` files to this repository.
