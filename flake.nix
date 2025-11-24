{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/7e567a3d092b7de69cdf5deaeb8d9526de230916";
    utils.url = "github:numtide/flake-utils";
  };
  outputs = inputs@{ nixpkgs, utils, ... }:
    utils.lib.eachSystem ["x86_64-linux"]
    (system:
      with nixpkgs.legacyPackages.${system}.python3Packages;
      let
        pkgs = nixpkgs.legacyPackages.${system};

        ngt = buildPythonPackage rec {
          pname = "ngt";
          version = "v1.12.3";
          src = pkgs.fetchFromGitHub {
            owner = "yahoojapan";
            repo = "NGT";
            rev = version;
            sha256 = "d2DUnuSlnMhd/QDJZRJLXQvcat37dEM+s9Ci4KXxxvQ=";
          };
          postPatch = ''
            substituteInPlace python/src/ngtpy.cpp \
              --replace "NGT_VERSION" '"${version}"'
          '';
          preConfigure = ''
            export HOME=$PWD
            export LD_LIBRARY_PATH=${pkgs.ngt}/lib
            cd python
          '';
          buildInputs = [ pkgs.ngt ];
          propagatedBuildInputs = [ numpy pybind11 ];
        };

        discord-py-slash-command = buildPythonPackage rec {
          pname = "discord-py-slash-command";
          version = "2.3.1";
          src = fetchPypi {
            inherit pname version;
            sha256 = "R2+lSV3WIZDg02F0Qbqn5ef6Mb/v73+I945CgWZsDUE=";
          };
          propagatedBuildInputs = [ aiohttp discordpy ];
        };

        discordhealthcheck = buildPythonPackage rec {
          pname = "discordhealthcheck";
          version = "0.0.8";
          src = pkgs.fetchFromGitHub {
            owner = "psidex";
            repo = "DiscordHealthCheck";
            rev = "f05bc47160db56629e0b502e6814b21d71b42cda";
            sha256 = "P8JGa9k8Df9bowsnD56nMLj9KimkcRShu7Ux5sc6yXU=";
          };
          propagatedBuildInputs = [ discordpy ];
        };

        logdecorator = buildPythonPackage rec {
          pname = "logdecorator";
          version = "2.2";
          src = fetchPypi {
            inherit pname version;
            sha256 = "jm0SWc9hW30nIHOacaO2Lbz68i2QI4K31BrIcvSh1tk=";
          };
        };

        en-core-web-md = buildPythonPackage rec {
          pname = "en-core-web-md";
          version = "3.0.0";
          src = pkgs.fetchzip {
            url =
              "https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.0.0/en_core_web_md-3.0.0.tar.gz";
            sha256 = "4UrUhHNVLHxbOdm3BIIetv4Pk86GzFoKoSnlvLFqesI=";
          };
          propagatedBuildInputs = [ spacy ];
        };

        axyn = buildPythonApplication rec {
          name = "axyn";
          src = ./.;
          postPatch = ''
            substituteInPlace axyn/__main__.py \
              --replace "DEBUG" "WARNING"
          '';
          SETUPTOOLS_SCM_PRETEND_VERSION = "version";
          nativeBuildInputs = [ setuptools-scm ];
          propagatedBuildInputs = [
            discord-py-slash-command
            discordhealthcheck
            discordpy
            en-core-web-md
            logdecorator
            ngt
            numpy
            spacy
            sqlalchemy
          ];
        };

      in {
        packages = { inherit axyn; };
        defaultPackage = axyn;
      });
}
