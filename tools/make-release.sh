#!/bin/bash

name="disable_compliance_notification"
version=$(./gradlew properties | grep ^version: | cut -d ':' -f2 | xargs)
mc_version=$(./gradlew properties | grep ^minecraft_version: | cut -d ':' -f2 | xargs)

./gradlew build

mkdir release/
cp forge/build/libs/$name-$version.jar release/$name-$version-$mc_version-forge.jar
cp fabric/build/libs/$name-$version.jar release/$name-$version-$mc_version-fabric.jar
cp quilt/build/libs/$name-$version.jar release/$name-$version-$mc_version-quilt.jar

