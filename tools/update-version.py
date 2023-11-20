#!/usr/bin/python3

import asyncio
import argparse
import json
import re


from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET


async def main():
    parser = argparse.ArgumentParser(
        prog='UpdateVersion',
        description='Update dependency to correct version of minecraft version')
    parser.add_argument('-t', '--to', required=True)
    args = parser.parse_args()
    to = args.to

    (fabapi, fabloader), frg, nfg, (pack, java), modmenu, cloth = await load_versions(to)

    reg = [
        ("minecraft_version", to),
        ("forge_version", frg),
        ("neoforge_version", nfg),
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
    futures = [fabric(mcv), forge(mcv), neoforge(mcv), mc_version(mcv), modrinth(mcv, 'modmenu'), modrinth(mcv, 'cloth-config')]
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
    mavenResp = urlXML(
        'https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml')

    fgVersionList = list(map(lambda x: x.text, mavenResp.findall("versioning/versions/version")))
    fgTargetMCList = list(filter(lambda x: f'{mcv}-' in x, fgVersionList))
    fgVersion = fgTargetMCList[0].split("-", 1)[1]

    return fgVersion

async def neoforge(mcv):
    mavenResp = urlXML(
        'https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml')

    nfVersionList = list(map(lambda x: x.text, mavenResp.findall("versioning/versions/version")))
    nfTargetMCList = list(filter(lambda x: f'{mcv[2:]}.' in x, nfVersionList))
    nfVersion = nfTargetMCList[-1]

    return nfVersion

async def neoforge(mcv):
    mavenResp = urlXML(
        'https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml')

    nfVersionList = list(map(lambda x: x.text, mavenResp.findall("versioning/versions/version")))
    nfTargetMCList = list(filter(lambda x: f'{mcv[2:]}.' in x, nfVersionList))
    nfVersion = nfTargetMCList[-1]

    return nfVersion


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
    # NeoForge Maven is using cloudflare that blocks urlopen user-agent
    req = Request(url, headers={'User-Agent': 'Gradle/8.1.1 (Windows 11;10.0;amd64) (Microsoft;17.0.7;17.0.7+7-LTS)'})
    response = urlopen(req)
    return ET.fromstring(response.read())


def urlJson(url):
    response = urlopen(url)
    return json.loads(response.read())


if __name__ == "__main__":
    asyncio.run(main())
