#!/usr/bin/python3

import argparse
import json
import re

from urllib.request import urlopen
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(
        prog='UpdateVersion',
        description='Update dependency to correct version of minecraft version')
    parser.add_argument('-t', '--to', required=True)
    args = parser.parse_args()
    to = args.to

    fabapi, fabloader = fabric(to)
    frg = forge(to)

    reg = [
        ("minecraft_version", to),
        ("forge_version", frg),
        ("fabric_loader_version", fabloader),
        ("fabric_api_version", fabapi.split("+")[0])
    ]

    with open('config.properties', 'r+', encoding='utf-8') as f:
        content = f.read()

        for key, value in reg:
            content = re.sub(f"{key}=(.+)", f"{key}={value}", content, flags = re.M)

        f.seek(0)
        f.write(content)
        f.truncate()


def fabric(mcv):
    loaderResp = urlJson('https://meta.fabricmc.net/v2/versions/loader')
    mavenResp = urlXML(
        'https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml')

    apiVersionList = list(map(lambda x: x.text, mavenResp.findall("versioning/versions/version")))
    apiTargetMCList = list(filter(lambda x: f'+{mcv}' in x, apiVersionList))

    apiVersion = apiTargetMCList[-1]
    loaderVersion = loaderResp[0]['version']

    return (apiVersion, loaderVersion)

def forge(mcv):
    #Using multimc meta for now.
    versions = urlJson("https://raw.githubusercontent.com/MultiMC/meta-multimc/master/net.minecraftforge/index.json")['versions']
    
    # using for expression for fast find
    version = forge_find(versions, mcv)

    if version is None:
        return None
    
    vs = version.split('.')
    if int(vs[1]) > 0:
        # return stable
        return f'{vs[0]}.{vs[1]}.0'
    return version
        

def forge_find(l, mcv):
    for i in l:
        # maybe there's other deps are...
        for j in i['requires']:
            if j['uid'] == 'net.minecraft' and j['equals'] == mcv:
                return i['version']
    return None



def urlXML(url):
    response = urlopen(url)
    return ET.fromstring(response.read())


def urlJson(url):
    response = urlopen(url)
    return json.loads(response.read())


if __name__ == "__main__":
    main()
