#!/usr/bin/python3

import asyncio
import argparse
import json
import re


from urllib.request import urlopen
import xml.etree.ElementTree as ET


async def main():
    parser = argparse.ArgumentParser(
        prog='UpdateVersion',
        description='Update dependency to correct version of minecraft version')
    parser.add_argument('-t', '--to', required=True)
    args = parser.parse_args()
    to = args.to

    (fabapi, fabloader), frg, (pack, java), modmenu, cloth = await load_versions(to)

    reg = [
        ("minecraft_version", to),
        ("forge_version", frg),
        ("pack_format", pack),
        ("java_version", java),
        ("fabric_loader_version", fabloader),
        ("fabric_api_version", fabapi.split("+")[0]),
        ("cloth_config_version", cloth.split("+")[0]),
        ("modmenu_version", modmenu)
    ]

    with open('config.properties', 'r+', encoding='utf-8', newline='\n') as f:
        content = f.read()

        for key, value in reg:
            content = re.sub(f"{key}=(.+)", f"{key}={value}", content, flags = re.M)

        f.seek(0)
        f.write(content)
        f.truncate()


async def load_versions(mcv):
    futures = [fabric(mcv), forge(mcv), mc_version(mcv), modrinth(mcv, 'modmenu'), modrinth(mcv, 'cloth-config')]
    return await asyncio.gather(*futures)


async def fabric(mcv):
    loaderResp = urlJson('https://meta.fabricmc.net/v2/versions/loader')
    mavenResp = urlXML(
        'https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml')

    apiVersionList = list(map(lambda x: x.text, mavenResp.findall("versioning/versions/version")))
    apiTargetMCList = list(filter(lambda x: f'+{mcv}' in x, apiVersionList))

    apiVersion = apiTargetMCList[-1]
    loaderVersion = loaderResp[0]['version']

    return (apiVersion, loaderVersion)

async def forge(mcv):
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


def modrinth_def_findver(l):
    ver = None
    for i in l:
        # return latest release version
        if i['version_type'] == 'release':
            return i['version_number']

        # set latest if no release
        if ver is None:
            ver = i['version_number']

    # return latest beta if no release
    return ver


async def modrinth(mcv, modid, findFunc = modrinth_def_findver):
    resp = urlJson(f'https://api.modrinth.com/v2/project/{modid}/version?game_versions=%5B%22{mcv}%22%5D')
    return findFunc(resp)


async def mc_version(mcv):
    resp = urlJson(f'https://mpthlee.github.io/minecraft-version-json/{mcv}/version.json')

    pack_ver = resp['pack_version']
    if (isinstance(pack_ver, str) or isinstance(pack_ver, int)):
        pack_ver = str(pack_ver)
    else:
        pack_ver = str(max(pack_ver['resource'], pack_ver['data']))

    java_ver = 8 # old version = 8
    try:
        java_ver = int(resp['java_version'])
    except:
        pass

    return (pack_ver, java_ver)


def urlXML(url):
    response = urlopen(url)
    return ET.fromstring(response.read())


def urlJson(url):
    response = urlopen(url)
    return json.loads(response.read())


if __name__ == "__main__":
    asyncio.run(main())
