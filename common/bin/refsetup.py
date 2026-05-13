#!/usr/bin/env python3
"""
Set up workspace for a new SUSE Technical Reference Document.

This script replicates the functionality of common/bin/refsetup.sh,
prompting the user for information about a new document and then
creating the directory structure, template files, and symbolic links
needed to begin authoring content.

Usage:
    Run from the 'references' directory:
        python3 ../common/bin/refsetup.py

    Or with command-line arguments (non-interactive):
        python3 ../common/bin/refsetup.py \
            --doctype gs \
            --suse-products rancher rke2 sles \
            --partner-name clearml \
            --partner-product clearml \
            --distinctive-text ai-lifecycle
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------
# Constants
# ---------------------------------------------------------------

SUSE_PRODUCTS = {
    "sles", "slessap", "slehpc", "slmicro", "slelp", "slert",
    "sleha", "slebci", "smlm", "rancher", "sto", "sec", "obs",
    "virt", "edge", "telco", "ai", "rke", "rke2", "k3s",
}

# Abbreviation-to-directory-name mapping for products that use
# a longer form in the file name.
PRODUCT_ALIASES = {
    "sto": "storage",
    "virt": "virtualization",
    "obs": "observability",
    "sec": "security",
}

VALID_DOCTYPES = {"gs", "ri", "rc", "ea"}

# Document type descriptions (used in help text)
DOCTYPE_HELP = """
  gs : Getting started guide
       An introduction to a joint SUSE + partner solution with
       step-by-step guidance to install, configure, and validate the
       solution in a non-production environment.
  ri : Reference implementation
       An architectural approach and basis for deployment of a solution
       featuring multiple elements of the SUSE product portfolio in a
       production environment.
  rc : Reference configuration
       A reference implementation with specified partner hardware and
       software.
  ea : Enterprise architecture
       A holistic overview of an enterprise landscape featuring joint
       SUSE and partner solutions.
"""

SUSE_PRODUCT_LIST = """
Abbrev.   | Product
----------|----------------------------------------------
sles      | SUSE Linux Enterprise Server
slessap   | SUSE Linux Enterprise Server for SAP applications
slehpc    | SUSE Linux Enterprise High Performance Computing
slmicro   | SUSE Linux Micro
slelp     | SUSE Linux Enterprise Live Patching
slert     | SUSE Linux Enterprise Real Time
sleha     | SUSE Linux Enterprise for High Availability
slebci    | SUSE Linux Enterprise Base Container Images
smlm      | SUSE Multi-Linux Manager
rancher   | SUSE Rancher Prime
sec       | SUSE Security
virt      | SUSE Virtualization
obs       | SUSE Observability
sto       | SUSE Storage
ai        | SUSE AI
edge      | SUSE Edge
telco     | SUSE Telco
rke       | Rancher Kubernetes Engine
rke2      | Rancher Kubernetes Engine 2
k3s       | K3s
"""


# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------

def resolve_product(abbrev: str) -> str:
    """Map an abbreviation to its canonical directory-name form."""
    return PRODUCT_ALIASES.get(abbrev, abbrev)


def current_git_branch() -> str:
    """Return the name of the current Git branch, or empty string."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def make_symlink(target: Path, link: Path) -> None:
    """Create a relative symbolic link if it does not already exist."""
    if link.exists() or link.is_symlink():
        return
    rel_target = os.path.relpath(target, link.parent)
    link.symlink_to(rel_target)


# ---------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------

def prompt_doctype() -> str:
    """Prompt the user for a document type."""
    while True:
        response = input(">> Document type (gs, ri, rc, ea, help) : ").strip().lower()
        if response == "help":
            print(DOCTYPE_HELP)
            continue
        if response in VALID_DOCTYPES:
            return response
        print(f"  Invalid input: '{response}'. Enter gs, ri, rc, ea, or help.")
        print(DOCTYPE_HELP)


def prompt_suse_products() -> str:
    """Prompt the user for one or more SUSE product abbreviations."""
    products: list[str] = []
    print(
        "- - - - - -\n"
        "- Identify the featured SUSE products by entering\n"
        "- one product abbreviation at a time.\n"
        "- When done, press ENTER with no value.\n"
        "-\n"
        "- Additional options:\n"
        "-   'help' : display accepted abbreviations.\n"
        "-   'clear': clear the product list and start over.\n"
        "-   CTRL+C : cancel and exit.\n"
        "- - - - - -"
    )
    while True:
        response = input(">> SUSE product : ").strip().lower()
        if response == "":
            if products:
                break
            print("  Please enter at least one SUSE product.")
            continue
        if response == "help":
            print(SUSE_PRODUCT_LIST)
            print(f'  Featured SUSE products so far: "{"-".join(products)}"')
            continue
        if response == "clear":
            products.clear()
            print('  Product list cleared.')
            continue
        if response in SUSE_PRODUCTS:
            products.append(resolve_product(response))
            print(f'  Featured SUSE products: "{"-".join(products)}"')
        else:
            print(f"  Invalid product abbreviation: '{response}'. Enter 'help' for the list.")
    return "-".join(products)


def prompt_partner_name() -> str:
    """Prompt the user for the primary partner name."""
    print(
        "- - - - - -\n"
        "- Enter the name of the primary partner.\n"
        "- - - - - -"
    )
    while True:
        response = input(">> Primary partner : ").strip()
        name = re.sub(r"\s+", "", response).lower()
        if name:
            return name
        print("  Partner name cannot be blank.")


def prompt_partner_product() -> str:
    """Prompt the user for the primary partner's product name (optional)."""
    print(
        "- - - - - -\n"
        "- Enter the name of the primary partner's product.\n"
        "- TIP: Leave blank if the product name is the same as the partner name.\n"
        "- - - - - -"
    )
    response = input(">> Primary partner's product : ").strip()
    if response:
        return re.sub(r"\s+", "", response).lower()
    return ""


def prompt_distinctive_text() -> str:
    """Prompt the user for optional distinctive/use-case text."""
    print(
        "- - - - - -\n"
        "- OPTIONAL: Enter distinctive text (e.g., a use case).\n"
        "- Leave blank to skip.\n"
        "- - - - - -"
    )
    response = input(">> Distinctive text : ").strip()
    if response:
        return response.lower().replace(" ", "-")
    return ""


# ---------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------

def build_document_base(
    doctype: str,
    suse_products: str,
    partner_name: str,
    partner_product: str,
    distinctive_text: str,
) -> str:
    """Construct the base filename from the collected inputs."""
    usecase_suffix = f"_{distinctive_text}" if distinctive_text else ""
    partner_prod_part = f"-{partner_product}" if partner_product else ""

    if doctype in ("rc", "gs"):
        return f"{doctype}_suse-{suse_products}_{partner_name}{partner_prod_part}{usecase_suffix}"
    else:
        return f"{doctype}_{suse_products}{usecase_suffix}"


def create_structure(
    doctype: str,
    suse_products: str,
    partner_name: str,
    partner_product: str,
    distinctive_text: str,
    references_dir: Path,
    common_root: Path,
) -> None:
    """Create the directory tree, copy templates, and set up symlinks."""

    document_base = build_document_base(
        doctype, suse_products, partner_name, partner_product, distinctive_text,
    )
    dest_dir_name = partner_name if doctype in ("rc", "gs") else "suse"
    dest = references_dir / dest_dir_name
    templates = common_root / "templates"

    # ----- Display the plan -----
    print()
    print("  Preparing to create the following structure:")
    print()
    print(f"  references")
    print(f"  └── {dest_dir_name}")
    print(f"      ├── DC-{document_base}")
    print(f"      ├── adoc")
    print(f"      │   ├── {document_base}.adoc")
    print(f"      │   ├── {document_base}-docinfo.xml")
    print(f"      │   └── {document_base}-vars.adoc")
    print(f"      ├── images -> media")
    print(f"      └── media")
    print(f"          └── src")
    print(f"              ├── png")
    print(f"              └── svg")
    print()

    # ----- Create directories -----
    dest.mkdir(parents=True, exist_ok=True)
    adoc_dir = dest / "adoc"
    adoc_dir.mkdir(exist_ok=True)

    # ----- DC file -----
    dc_file = dest / f"DC-{document_base}"
    if dc_file.exists():
        print(f"  ERROR: '{dc_file.name}' already exists in '{dest_dir_name}'.")
        print("  Re-run with different input.")
        sys.exit(4)
    shutil.copy2(templates / "template_DC", dc_file)

    # ----- Symlinks to common adoc files -----
    common_adoc = common_root / "adoc"
    for name in (
        "common_gfdl1.2_i.adoc",
        "common_sbp_legal_notice.adoc",
        "common_trd_legal_notice.adoc",
        "common_docinfo_vars.adoc",
    ):
        make_symlink(common_adoc / name, adoc_dir / name)

    # ----- Docinfo XML -----
    docinfo_file = adoc_dir / f"{document_base}-docinfo.xml"
    if not docinfo_file.exists():
        shutil.copy2(templates / "template_docinfo", docinfo_file)

    # ----- Vars file -----
    vars_file = adoc_dir / f"{document_base}-vars.adoc"
    if not vars_file.exists():
        shutil.copy2(templates / "template_vars", vars_file)

    # ----- Main adoc file -----
    main_template_name = f"template_main-{doctype}"
    main_template = templates / main_template_name
    main_file = adoc_dir / f"{document_base}.adoc"
    if not main_file.exists():
        if main_template.exists():
            shutil.copy2(main_template, main_file)
        else:
            # Fallback: use the gs template if the specific one is missing
            print(f"  WARNING: Template '{main_template_name}' not found; using 'template_main-gs'.")
            shutil.copy2(templates / "template_main-gs", main_file)

    # ----- Media directories -----
    (dest / "media" / "src" / "png").mkdir(parents=True, exist_ok=True)
    (dest / "media" / "src" / "svg").mkdir(parents=True, exist_ok=True)

    # ----- Symlink to SUSE logo -----
    suse_logo = common_root / "images" / "src" / "svg" / "suse.svg"
    make_symlink(suse_logo, dest / "media" / "src" / "svg" / "suse.svg")

    # ----- images -> media symlink -----
    make_symlink(dest / "media", dest / "images")

    # ----- Update inter-document references -----
    # Main adoc: replace template_vars reference with actual vars filename
    if main_file.exists():
        content = main_file.read_text()
        content = content.replace(
            "include::./template_vars[]",
            f"include::./{document_base}-vars.adoc[]",
        )
        main_file.write_text(content)

    # DC file: replace template_main reference with actual adoc filename
    if dc_file.exists():
        content = dc_file.read_text()
        content = content.replace(
            'MAIN="template_main"',
            f'MAIN="{document_base}.adoc"',
        )
        dc_file.write_text(content)

    # ----- Success banner -----
    print()
    print("= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =")
    print("= Workspace for your new guide has been set up.")
    print("=")
    print(f"= Access your workspace in:")
    print(f"=   references/{dest_dir_name}")
    print("= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =")
    print()


# ---------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up workspace for a new SUSE Technical Reference Document.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Interactive mode:\n"
            "    python3 refsetup.py\n\n"
            "  Non-interactive mode:\n"
            "    python3 refsetup.py --doctype gs \\\n"
            "        --suse-products rancher rke2 sles \\\n"
            "        --partner-name clearml \\\n"
            "        --partner-product clearml \\\n"
            "        --distinctive-text ai-lifecycle\n"
        ),
    )
    parser.add_argument(
        "--doctype", "-t",
        choices=sorted(VALID_DOCTYPES),
        help="Document type (gs, ri, rc, ea).",
    )
    parser.add_argument(
        "--suse-products", "-s",
        nargs="+",
        help="One or more SUSE product abbreviations.",
    )
    parser.add_argument(
        "--partner-name", "-p",
        default="",
        help="Primary partner name (required for gs/rc types).",
    )
    parser.add_argument(
        "--partner-product",
        default="",
        help="Primary partner product name (optional).",
    )
    parser.add_argument(
        "--distinctive-text", "-d",
        default="",
        help="Optional distinctive / use-case text appended to filenames.",
    )
    parser.add_argument(
        "--skip-branch-check",
        action="store_true",
        help="Skip the Git branch safety check.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main() -> None:
    args = parse_args()
    interactive = args.doctype is None

    # -- Resolve paths --
    references_dir = Path.cwd()
    common_root = references_dir.parent / "common"

    # -- Display banner --
    print()
    print("= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =")
    print("= Set up workspace for a new technical reference document   =")
    print("= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =")
    print()

    # -- Verify working directory --
    if not references_dir.name == "references":
        print(f"  ERROR: Current directory is '{references_dir}'.")
        print("  Please change to the 'references' directory first.")
        sys.exit(2)

    # -- Verify Git branch --
    if not args.skip_branch_check:
        branch = current_git_branch()
        if branch == "main":
            print("  ERROR: You are on the 'main' branch.")
            print("  Create and check out a feature branch, then re-run.")
            sys.exit(1)

    # -- Verify common directory exists --
    if not common_root.is_dir():
        print(f"  ERROR: Common directory not found at '{common_root}'.")
        sys.exit(3)

    # -- Collect inputs (interactive or from CLI args) --
    if interactive:
        print(" This script will prompt you for information about your")
        print(" document, then use your responses to create the directories")
        print(" and template files you will need.")
        print()
        input("Press ENTER to continue or CTRL+C to cancel.")
        print()

        doctype = prompt_doctype()
        suse_products = prompt_suse_products()

        partner_name = ""
        partner_product = ""
        if doctype in ("rc", "gs"):
            partner_name = prompt_partner_name()
            partner_product = prompt_partner_product()

        distinctive_text = prompt_distinctive_text()
    else:
        doctype = args.doctype
        # Validate and resolve SUSE products
        if not args.suse_products:
            print("  ERROR: --suse-products is required in non-interactive mode.")
            sys.exit(1)
        resolved = []
        for p in args.suse_products:
            p_lower = p.lower()
            if p_lower not in SUSE_PRODUCTS:
                print(f"  ERROR: Unknown SUSE product abbreviation: '{p_lower}'.")
                print(SUSE_PRODUCT_LIST)
                sys.exit(1)
            resolved.append(resolve_product(p_lower))
        suse_products = "-".join(resolved)

        partner_name = re.sub(r"\s+", "", args.partner_name).lower()
        partner_product = re.sub(r"\s+", "", args.partner_product).lower()
        distinctive_text = args.distinctive_text.lower().replace(" ", "-")

        if doctype in ("rc", "gs") and not partner_name:
            print("  ERROR: --partner-name is required for gs/rc document types.")
            sys.exit(1)

    # -- Confirm before proceeding (interactive only) --
    if interactive:
        document_base = build_document_base(
            doctype, suse_products, partner_name, partner_product, distinctive_text,
        )
        dest_name = partner_name if doctype in ("rc", "gs") else "suse"
        print()
        print(f"  Document type     : {doctype}")
        print(f"  SUSE products     : {suse_products}")
        if partner_name:
            print(f"  Partner name      : {partner_name}")
        if partner_product:
            print(f"  Partner product   : {partner_product}")
        if distinctive_text:
            print(f"  Distinctive text  : {distinctive_text}")
        print(f"  Base filename     : {document_base}")
        print(f"  Destination dir   : references/{dest_name}")
        print()
        input(">> Press ENTER to create document structure or CTRL+C to cancel.")
        print()

    # -- Create the structure --
    create_structure(
        doctype=doctype,
        suse_products=suse_products,
        partner_name=partner_name,
        partner_product=partner_product,
        distinctive_text=distinctive_text,
        references_dir=references_dir,
        common_root=common_root,
    )


if __name__ == "__main__":
    main()
