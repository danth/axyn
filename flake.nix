{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
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
          version = "v2.5.0";

          src = pkgs.fetchFromGitHub {
            owner = "yahoojapan";
            repo = "NGT";
            rev = version;
            hash = "sha256-2cCuVeg7y3butTIAQaYIgx+DPqIFEA2qqVe3exAoAY8=";
          };

          postPatch = ''
            substituteInPlace python/src/ngtpy.cpp \
              --replace-fail "NGT_VERSION" '"${version}"'
          '';

          preConfigure = ''
            export HOME=$PWD
            cd python
          '';

          format = "pyproject";
          build-system = [ setuptools ];
          buildInputs = [ pkgs.ngt ] ++ pkgs.ngt.buildInputs;
          propagatedBuildInputs = [ numpy pybind11 ];
        };

        discordhealthcheck = buildPythonPackage rec {
          pname = "discordhealthcheck";
          version = "0.1.1";

          src = pkgs.fetchFromGitHub {
            owner = "psidex";
            repo = "DiscordHealthCheck";
            rev = "1822ca34190fb34cb51779876ba3aebd760219fb";
            hash = "sha256-icFlbOTJtFfZJC4A4Fz7c6/aXT1vaFgmkBbBmdScBxM=";
          };

          format = "pyproject";
          build-system = [ setuptools ];
          propagatedBuildInputs = [ discordpy ];
        };

        logdecorator = buildPythonPackage rec {
          pname = "logdecorator";
          version = "2.2";

          src = fetchPypi {
            inherit pname version;
            sha256 = "jm0SWc9hW30nIHOacaO2Lbz68i2QI4K31BrIcvSh1tk=";
          };

          format = "pyproject";
          build-system = [ setuptools ];
        };

        en-core-web-md = buildPythonPackage rec {
          pname = "en-core-web-md";
          version = "3.8.0";

          src = pkgs.fetchzip {
            url = "https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0.tar.gz";
            hash = "sha256-0+W2x+xUYrHs4e+EibhoRcxXMfC8SnUXVK1Lh/RiIaU=";
          };

          format = "pyproject";
          build-system = [ setuptools ];
          propagatedBuildInputs = [ spacy ];
        };

        axyn = buildPythonApplication rec {
          name = "axyn";
          src = ./.;

          format = "pyproject";
          build-system = [ setuptools setuptools-scm ];
          SETUPTOOLS_SCM_PRETEND_VERSION = "0.0.0";

          postPatch = ''
            substituteInPlace axyn/__main__.py \
              --replace-fail "DEBUG" "WARNING"
          '';

          propagatedBuildInputs = [
            discordhealthcheck
            discordpy
            en-core-web-md
            logdecorator
            ngt
            numpy
            spacy
            sqlalchemy_1_4
          ];
        };

      in {
        packages = { inherit axyn; };
        defaultPackage = axyn;
      });
}
