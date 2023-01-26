#!/bin/bash

name="disable_compliance_notification"

cd forge
version=$(./gradlew properties | grep ^version: | cut -d ':' -f2 | xargs)

chmod +x ./gradlew
./gradlew build

cd ../fabric

chmod +x ./gradlew
./gradlew build

cd ../
mkdir release/
cp forge/build/libs/$name-forge-$version.jar release/
cp fabric/build/libs/$name-fabric-$version-fabric.jar release/