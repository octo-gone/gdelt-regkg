"""Prediction compatibility fingerprints and explicit spaCy device selection."""

import sys
from importlib import metadata, util
from pathlib import Path

from gdelt_regkg.dependencies import require_dependency
from gdelt_regkg.utils import read_resource_json, resource_path

from .storage import digest


def file_hash(path):
    import hashlib

    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            checksum.update(block)
    return checksum.hexdigest()


def select_device(device, gpu_id, progress):
    if device != "cpu":
        installed = []
        for distribution in ("cupy-cuda12x", "cupy-cuda13x"):
            try:
                metadata.version(distribution)
                installed.append(distribution)
            except metadata.PackageNotFoundError:
                pass
        if len(installed) > 1:
            raise ValueError(
                "Both CUDA 12 and CUDA 13 CuPy wheels are installed. "
                "Uninstall the unused cupy-cuda12x or cupy-cuda13x wheel, "
                "then reinstall the compatible CuPy wheel."
            )
    # Windows PyTorch wheels register their bundled CUDA DLL directories when
    # imported. Let CuPy discover those libraries before Thinc probes its backend.
    if device != "cpu" and sys.platform == "win32" and util.find_spec("torch") is not None:
        require_dependency("torch", "translate")
    spacy = require_dependency("spacy", "ner")

    if device != "cpu":
        try:
            spacy.require_gpu(gpu_id)
            # Check computation too: importing CuPy alone doesn't verify its runtime.
            cupy = require_dependency("cupy", "ner")

            cupy.arange(4).sum().item()
            progress(f"[benchmark] NER device: cuda:{gpu_id}")
            return f"cuda:{gpu_id}"
        except (OSError, ValueError, RuntimeError) as error:
            if device == "cuda":
                raise ValueError(
                    "spaCy CUDA initialization failed. Install one CuPy variant separately: "
                    'python -m pip install "cupy-cuda12x[ctk]" for CUDA 12, or '
                    'python -m pip install "cupy-cuda13x[ctk]" for CUDA 13. '
                    f"Use a compatible NVIDIA driver, or select --device cpu. {error}"
                ) from error
            progress(f"[benchmark] CUDA unavailable; using CPU: {error}")
    spacy.require_cpu()
    progress("[benchmark] NER device: cpu")
    return "cpu"


def prediction_signature(args, fields, device):
    defaults = read_resource_json("defaults.json", resources_dir=args.resources_dir)
    selected = set(fields)
    needs = set()
    if "tone" in selected:
        needs.add("tone")
    if selected & {"themes", "enhanced_themes"}:
        needs.add("themes")
    if selected & {"counts", "enhanced_counts"}:
        needs.update(("counts", "locations", "ner"))
    if selected & {
        "persons",
        "enhanced_persons",
        "organizations",
        "enhanced_organizations",
        "all_names",
        "locations",
        "enhanced_locations",
    }:
        needs.add("ner")
    if selected & {"locations", "enhanced_locations"}:
        needs.add("locations")
    if "gcam" in selected and args.gcam_lexicon is None:
        needs.add("gcam")
    resources = {
        name: file_hash(resource_path("lexicons", defaults[name], resources_dir=args.resources_dir))
        for name in sorted(needs)
    }
    if args.gcam_lexicon:
        resources["gcam"] = file_hash(args.gcam_lexicon)
    if args.ner_cache:
        resources["ner_cache"] = file_hash(args.ner_cache)
    elif "ner" in needs:
        model = Path(args.ner_model)
        if not model.is_dir():
            try:
                spec = util.find_spec(args.ner_model)
            except (ModuleNotFoundError, ValueError):
                spec = None
            if spec is None or spec.origin is None:
                raise ValueError(f"Install spaCy model {args.ner_model!r} before benchmarking")
            model = Path(spec.origin).parent
        resources["model"] = digest(
            {
                str(p.relative_to(model)): file_hash(p)
                for p in sorted(model.rglob("*"))
                if p.is_file() and "__pycache__" not in p.parts
            }
        )
    root = Path(__file__).resolve().parents[1]
    code_paths = [
        *root.joinpath("fields").glob("*.py"),
        *(
            root / n
            for n in (
                "pipeline.py",
                "profiles.py",
                "record.py",
                "utils.py",
                "wire.py",
                "dependencies.py",
                "types.py",
            )
        ),
        Path(__file__).with_name("corpus.py"),
    ]
    versions = {}
    for name in ("spacy", "thinc", "numpy", "cupy-cuda12x", "cupy-cuda13x"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    configuration = {
        "schema": 1,
        "fields": sorted(fields),
        "resources": resources,
        "code": {str(p.relative_to(root)): file_hash(p) for p in code_paths},
        "versions": versions,
        "device": device,
        "batch_size": args.batch_size,
        "batch_chars": args.batch_chars,
        "numeric_date_order": args.numeric_date_order,
    }
    return digest(configuration)


def article_signature(namespace, reference, article):
    # Body hashes are checked when loading the corpus. Include supplied media,
    # provenance and metadata, not native extraction targets used only for scoring.
    return digest(
        {
            "configuration": namespace,
            "article": {k: v for k, v in article.items() if k not in {"text", "native_cells"}},
            "metadata": {
                k: reference.get(k)
                for k in ("recordid", "date", "source_collection", "source", "document")
            },
        }
    )
