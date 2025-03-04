#!/usr/bin/env python3

__doc__ = \
"""The Developmental Cognition and Neuroimaging (DCAN) lab fMRI Pipeline [1].
This BIDS application initiates a functional MRI processing pipeline built
upon the Human Connectome Project's minimal processing pipelines [2].  The
application requires only a dataset conformed to the BIDS specification, and
little-to-no additional configuration on the part of the user. BIDS format
and applications are explained in detail at http://bids.neuroimaging.io/
"""
__references__ = \
"""References
----------
[1] dcan-pipelines (for now, please cite [3] in use of this software)
[2] Glasser, MF. et al. The minimal preprocessing pipelines for the Human
Connectome Project. Neuroimage. 2013 Oct 15;80:105-24.
10.1016/j.neuroimage.2013.04.127
[3] Fair, D. et al. Correction of respiratory artifacts in MRI head motion
estimates. Biorxiv. 2018 June 7. doi: https://doi.org/10.1101/337360
[4] Dale, A.M., Fischl, B., Sereno, M.I., 1999. Cortical surface-based
analysis. I. Segmentation and surface reconstruction. Neuroimage 9, 179-194.
[5] M. Jenkinson, C.F. Beckmann, T.E. Behrens, M.W. Woolrich, S.M. Smith. FSL.
NeuroImage, 62:782-90, 2012
[6] Avants, BB et al. The Insight ToolKit image registration framework. Front
Neuroinform. 2014 Apr 28;8:44. doi: 10.3389/fninf.2014.00044. eCollection 2014.
"""
__version__ = "1.0.1"

import argparse
import os

from helpers import (read_bids_dataset, validate_config, validate_license)
from pipelines import (ParameterSettings, PreFreeSurfer, FreeSurfer,
                       PostFreeSurfer, FMRIVolume, FMRISurface,
                       DCANBOLDProcessing, ExecutiveSummary, CustomClean,
                       FileMapper)


def _cli():
    """
    command line interface
    :return:
    """
    parser = generate_parser()
    args = parser.parse_args()

    kwargs = {
        'bids_dir': args.bids_dir,
        'output_dir': args.output_dir,
        'aseg': args.aseg,
        'atropos_mask_method': args.atropos_mask_method,
        'atropos_range': args.atropos_range,
        'bandstop_params': args.bandstop,
        'dcmethod': args.dcmethod,
        'freesurfer_license': args.freesurfer_license,
        'hyper_norm_method': args.hyper_norm_method,
        'jlf_method': args.jlf_method,
        'max_cortical_thickness': args.max_cortical_thickness,
        'mc_frame': args.mc_frame,
        'multi_masking_dir': args.multi_masking_dir,
        'multi_template_dir': args.multi_template_dir,
        'no_crop': args.no_crop,
        'subject_list': args.subject_list,
        'session_list': args.session_list,
        'smoothing_iterations': args.smoothing_iterations,
        'subcortical_map_method': args.subcortical_map_method,
        't1_brain_mask': args.t1_brain_mask,
        't1_study_template': args.t1_study_template,
        't2_study_template': args.t2_study_template,
        'anat_only': args.anat_only,
        'cleaning_json': args.cleaning_json,
        'file_mapper_json': args.file_mapper_json,
        'check_only': args.check_outputs_only,
        'ignore_expected_outputs': args.ignore_expected_outputs,
        'ncpus': args.ncpus,
        'print_commands': args.print_commands,
        'stages': args.stages
    }

    return interface(**kwargs)


def generate_parser(parser=None):
    """
    Generates the command line parser for this program.
    :param parser: optional subparser for wrapping this program as a submodule.
    :return: ArgumentParser for this script/module
    """
    if not parser:
        parser = argparse.ArgumentParser(
            prog='run.py',
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=__references__
        )
    # Positional/Required args:
    parser.add_argument(
        'bids_dir',
        help='path to the input bids dataset root directory.  Read more '
             'about bids format in the link in the description.  It is '
             'recommended to use the dcan bids gui or dcm2bids to convert '
             'from participant dicoms to bids.'
    )
    parser.add_argument(
        'output_dir',
        help='path to the output directory for all intermediate and output '
             'files from the pipeline, also path in which logs are stored.'
    )
    # Optional args (now sorted alphabetically:
    parser.add_argument(
        '--aseg', type=str, dest='aseg',
        default='DEFAULT',
        metavar='PATH',
        help='specify path to the aseg file to be used by FreeSurfer. '
             'Default: aseg generated by PreFreeSurfer. '
    )
    parser.add_argument(
        '--atropos-mask-method', dest='atropos_mask_method',
        default='REFINE',
        choices=['REFINE', 'CREATE', 'NONE'],
        help='We create a mask (T1w_acpc_brain_mask.nii.gz) near the top of '
             'PreFreeSurfer. Later, we refine the mask using atropos. In some '
             'cases we just want to use the mask that atropos creates during the '
             'refinement step to overwrite the original mask. To do that, set '
             'this option to CREATE. Other times, we may want to keep the mask '
             'as-is, in which case, use NONE. Tip: for neos, use REFINE; for '
             'older babies (8+?) use CREATE. '
             'Default: REFINE.'
    )
    parser.add_argument(
        '--atropos-range', type=int, nargs=2, dest='atropos_range',
        default=(4,5),
        metavar=('LOWER', 'UPPER'),
        help='range to be used for atropos labeling. '
             'Defaults: 4 and 5. '
    )
    parser.add_argument(
        '--bandstop', type=float, nargs=2,
        metavar=('LOWER', 'UPPER'),
        help='parameters for motion regressor band-stop filter. It is '
             'recommended for the boundaries to match the inter-quartile '
             'range for participant group respiratory rate (bpm), or to match '
             'bids physio data directly [3].  These parameters are highly '
             'recommended for data acquired with a frequency of approx. 1 Hz '
             'or more (TR<=1.0). Default: no filter'
    )
    parser.add_argument(
        '--dcmethod',
        choices=['TOPUP', 'FIELDMAP', 'T2_DC', 'NONE'],
        help='specify a distortion correction method. Default: use auto-'
             'detection. '
    )
    parser.add_argument(
        '--freesurfer-license', dest='freesurfer_license',
        metavar='PATH',
        help='If using docker or singularity, you will need to acquire and '
             'provide your own FreeSurfer license. The license can be '
             'acquired by filling out this form: '
             'https://surfer.nmr.mgh.harvard.edu/registration.html '
    )
    parser.add_argument(
        '--hyper-normalization-method', dest='hyper_norm_method',
        default='ADULT_GM_IP',
        choices=['ADULT_GM_IP', 'ROI_IPS', 'NONE'],
        help='specify the intensity profiles to use for the hyper-'
             'normalization step in FreeSurfer: \n'
             'ADULT_GM_IP adjusts the entire base image such that the IP '
             'of GM in the target roughly matches the IP of GM of the '
             'reference (i.e., the adult freesurfer atlas). Then the WM '
             'is shifted in the target image to match the histogram of WM '
             'in the reference. \n'
             'ROI_IPS adjusts the intensity profiles of each ROI (GM, WM, '
             'CSF) separately and reassembles the parts. '
             'NONE skips hyper-normalization step. This allows the user '
             'to run PreFreeSurfer, apply new, experimental hyper-'
             'normalization methods and then restart at FreeSurfer. \n'
             'Default: ADULT_GM_IP.'
    )
    parser.add_argument(
        '--jlf-method', type=str, dest='jlf_method',
        default="T1W",
        choices=['T1W', 'T2W', 'T1W_ORIG'],
        help='specify method to use to perform joint label fusion '
             'Default: T1W.'
    )
    parser.add_argument(
        '--max-cortical-thickness', type=int, dest='max_cortical_thickness',
        default=5,
        metavar='MM',
        help='maximum cortical thickness to allow in FreeSurfer. '
             'Default: 5 mm. '

    )
    parser.add_argument(
        '--motion-control-frame', '--mc-frame', dest='mc_frame',
        default=17,
        metavar='FRAME',
        help='frame to be used when computing motion-control values. This '
             'choosing different frames to see what works best for a run. In '
             'future, will add an algorithm to determine best frame(s). '
             'Default: 17'
    )
    parser.add_argument(
        '--multi-masking-dir', dest='multi_masking_dir',
        metavar='PATH',
        help='directory for joint label fusion masks.'
    )
    parser.add_argument(
        '--multi-template-dir', dest='multi_template_dir',
        metavar='PATH',
        help='directory for joint label fusion templates. It should contain '
             'only folders which each contain a "T1w_brain.nii.gz" and a '
             '"Segmentation.nii.gz". Each subdirectory may have any name and '
             'any number of additional files.'
    )
    parser.add_argument(
        '--no-crop', dest='no_crop', action='store_true',
        help='alignment in PreFreeSurfer does neck/shoulder cropping. Some '
             'images do not have neck and shoulders, so do not want this '
             'cropping to happen. This option allows user to turn that off. '
    )
    parser.add_argument(
        '--participant-label', dest='subject_list', nargs='+',
        metavar='LABEL',
        help='optional list of participant ids to run. Default is all ids '
             'found under the bids input directory.  A participant label '
             'does not include "sub-"'
    )
    parser.add_argument(
        '--session-id', dest='session_list', nargs='*',
        metavar='LABEL',
        help='filter input dataset by session id. Default is all ids '
             'found under the subject input directory(s).  A session id '
             'does not include "ses-"'
    )
    parser.add_argument(
        '--smoothing-iterations', type=int, dest='smoothing_iterations',
        metavar='ITERATIONS',
        default=10,
        help='Tell FreeSurfer how many smoothing iterations to run. '
             'Default: 10 iterations. '
    )
    parser.add_argument(
        '--subcortical-map-method', dest='subcortical_map_method',
        choices=['ROI_MAP', 'MNI_AFFINE'], default="ROI_MAP",
        help='specify method to use to align subcorticals. '
             'Default: ROI_MAP.'
    )
    parser.add_argument(
        '--T1-brain-mask', type=str, dest='t1_brain_mask',
        default=None,
        metavar='PATH',
        help='specify the path to the mask file. The file specified must be aligned '
             'with the T1w image. The mask will first be copied into the T1w folder '
             'as T1w_brain_mask.nii.gz. It will then be ACPC aligned, using the '
             'matrix generated when aligning the T1w image. The result will be '
             'written to T1w/T1w_acpc_brain_mask.nii.gz. '
             'Tip: when supplying a brain-mask, you may want to set '
             '--atropos-mask-method to NONE. '
             'Default: mask generated by PreFreeSurfer. '
    )
    parser.add_argument(
        '--t1-study-template', nargs=2,
        default=(None, None),
        metavar=('HEAD', 'BRAIN'),
        help='T1w template head and brain images for intermediate nonlinear '
             'registration, effective where population differs greatly from '
             'average adult, e.g. in elderly populations with large '
             'ventricles.'
    )
    parser.add_argument(
        '--t2-study-template', nargs=2,
        default=(None, None),
        metavar=('HEAD', 'BRAIN'),
        help='T2w template head and brain images for intermediate nonlinear '
             'registration, effective where population differs greatly from '
             'average adult, e.g. in elderly populations with large '
             'ventricles.'
    )

    # Specifying pipeline stages.
    extras = parser.add_argument_group(
        'special pipeline options',
        description='options which pertain to an alternative pipeline or an '
        'extra stage. '
    )
    extras.add_argument(
        '--anat-only', '--ignore-func', dest='anat_only',
        action='store_true',
        help='Ignore functional files (process anatomy files only). This option '
             'must be set in order to process subjects for which no functional '
             'data was collected. '
    )
    extras.add_argument(
        '--custom-clean', dest='cleaning_json',
        metavar='PATH',
        help='runs dcan cleaning script after the pipeline completes '
             'successfully, to delete pipeline outputs based on the file '
             'structure specified in the custom-clean json.'
    )
    extras.add_argument(
        '--file-mapper-json', dest='file_mapper_json',
        metavar='PATH',
        help='runs dcan file-mapper after the pipeline completes '
             'successfully, to copy pipeline outputs to BIDS-formatted '
             'derivatives files based on the file-mapper json.'
    )

    # What/how to run.
    runopts = parser.add_argument_group(
        'runtime options',
        description='Run-time instructions. These options are not passed to '
        'the stages. Rather, they control what and how the pipeline is run.'
    )
    runopts.add_argument(
        '--check-outputs-only', action='store_true',
        help='checks for the existence of outputs for each stage then exit. '
             'Useful for debugging.'
    )
    runopts.add_argument(
        '--ignore-expected-outputs', action='store_true',
        help='continues pipeline even if some expected outputs are missing.'
    )
    runopts.add_argument(
        '--ncpus', type=int,
        default=1,
        help='number of cores to use for concurrent processing and '
             'algorithmic speedups.  Warning: causes ANTs and FreeSurfer to '
             'produce non-deterministic results. '
             'Default: 1.'
    )
    runopts.add_argument(
        '--print-commands-only', action='store_true', dest='print_commands',
        help='print run commands for each stage to shell then exit.'
    )
    runopts.add_argument(
        '--stage','--stages', dest='stages',
        metavar='STAGE',
        help='specify a subset of stages to run.'
             'If a single stage name is given, the pipeline with be '
             'started at that stage. If a string with a ":" is given, '
             'a stage name before the ":" will tell run.py where to '
             'start and a stage name after the ":" will tell it where '
             'to stop. If no ":" is found, the pipeline will start '
             'with the stage specified and run to the end. '
             'Calling run.py with: \n'
             '   --stage="PreFreeSurfer:PreFreeSurfer"  \n'
             'or with: \n'
             '   --stage=":PreFreeSurfer"  \n'
             'will cause only PreFreeSurfer to be run. '
             '(This can be useful to do optional processing between'
             'PreFreeSurfer and FreeSurfer.)'
             'Calling run.py with: \n'
             '   --stages="FreeSurfer:FMRISurface"  \n'
             'will start with stage FreeSurfer and stop after'
             'FMRISurface (before DCANBOLDProcessing).'
             'Default start is PreFreeSurfer and default '
             'stop is ExecutiveSummary. The specifications: \n'
             '   --stages="PreFreeSurfer:ExecutiveSummary"  \n'
             '   --stages=":ExecutiveSummary"  \n'
             '   --stages="PreFreeSurfer:"  \n'
             'are exactly identical to each other and to sending '
             'no --stage argument. '
             'Valid stage names: '
             'PreFreeSurfer, FreeSurfer, PostFreeSurfer, FMRIVolume, '
             'FMRISurface, DCANBOLDProcessing, ExecutiveSummary '
    )
    runopts.add_argument(
        '--version', '-v', action='version', version='%(prog)s ' + __version__
    )

    return parser


def interface(bids_dir, output_dir, subject_list=None, session_list=None,
              aseg="DEFAULT", atropos_mask_method=None, atropos_range=None,
              bandstop_params=None, dcmethod=None, freesurfer_license=None,
              hyper_norm_method=None,
              jlf_method=None, max_cortical_thickness=5, mc_frame=17,
              multi_masking_dir=None, multi_template_dir=None, no_crop=False,
              smoothing_iterations=10,
              subcortical_map_method=None, t1_brain_mask=None,
              t1_study_template=None, t2_study_template=None,
              anat_only=False, cleaning_json=None, file_mapper_json=None,
              check_only=False, ignore_expected_outputs=False, ncpus=1,
              print_commands=False, stages=None):
    """
    main application interface
    :param bids_dir: input bids dataset see "helpers.read_bids_dataset" for more info.
    :param output_dir: output folder.
    :param subject_list: subject list filtering. See "helpers.read_bids_dataset".
    :param session_list: session list filtering. See "helpers.read_bids_dataset".
    :param aseg: path to aseg file to be used in FreeSurfer.
    :param atropos_mask_method: refine the mask, create a new mask, or leave as-is.
    :param atropos_range: tuple of lower and upper bounds for ANTs/Atropos labels.
    :param bandstop_params: tuple of lower and upper bounds for stop-band filter.
    :param dcmethod: which method will be used for distortion correction.
    :param freesurfer_license: path to license to use FreeSurfer.
    :param hyper_norm_method: which method will be used for hyper-normalization step.
    :param jlf_method: which method to use for joint label fusion.
    :param max_cortical_thickness: maximum cortical thickness allowed in FreeSurfer.
    :param mc_frame: frame to be used when computing motion control values.
    :param multi_masking_dir: directory containing masks for JLF.
    :param multi_template_dir: directory containing templates for JLF.
    :param no_crop: allow user to turn off neck/shoulder cropping.
    :param smoothing_iterations: specify number of smoothing iterations to FreeSurfer.
    :param subcortical_map_method: method by which to generate subcortical segmentations.
    :param t1_brain_mask: specify mask to use instead of letting PreFreeSurfer create it.
    :param t1_study_template (a tuple): templates for brain and head masking.
    :param t2_study_template (a tuple): templates for brain and head masking.
    :param anat_only: process anatomy data only.
    :param cleaning_json: input to CustomClean to indicate what files to delete.
    :param file_mapper_json: input to FileMapper.
    :param check_only: check expected outputs for each stage then terminate.
    :param ignore_expected_outputs: ignore the expected outputs from each stage.
    :param ncpus: number of cores for parallelized processing.
    :param print_commands: print commands but don't execute them.
    :param stages: only run a subset of stages.
    :return:
    """
    if not check_only and not print_commands:
        validate_license(freesurfer_license)
    # Read from bids dataset.
    assert os.path.isdir(bids_dir), bids_dir + ' is not a directory!'
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    session_generator = read_bids_dataset(
        bids_dir, subject_list=subject_list, session_list=session_list)

    # Run each session in serial.
    for session in session_generator:
        # Setup session configuration.
        out_dir = os.path.join(
            output_dir,
            'sub-%s' % session['subject'],
            'ses-%s' % session['session']
        )

        # detect available data for pipeline stages
        validate_config(session, anat_only)
        modes = session['types']
        run_anat = 'T1w' in modes
        run_func = 'bold' in modes and not anat_only
        run_summary = True

        # Set user input parameters for this session, before initializing
        # each stage with the session specification (below).
        session_spec = ParameterSettings(session, out_dir)

        session_spec.set_anat_only(anat_only)

        if aseg is not None:
            session_spec.set_aseg(aseg)

        if atropos_mask_method is not None:
            session_spec.set_atropos_mask_method(atropos_mask_method)

        if atropos_range is not None:
            session_spec.set_atropos_range(*atropos_range)

        if bandstop_params is not None:
            session_spec.set_bandstop_filter(*bandstop_params)

        if dcmethod is not None:
            session_spec.set_dcmethod(dcmethod)

        if hyper_norm_method is None:
            # Default is ADULT_GM_IP.
            session_spec.set_hypernormalization_method("ADULT_GM_IP")
        else:
            session_spec.set_hypernormalization_method(hyper_norm_method)

        if jlf_method is not None:
            session_spec.set_jlf_method(jlf_method)

        if max_cortical_thickness is not 5:
            session_spec.set_max_cortical_thickness(max_cortical_thickness)

        session_spec.set_smoothing_iterations(smoothing_iterations)

        if subcortical_map_method is not None:
            session_spec.set_subcortical_map_method(subcortical_map_method)

        if t1_brain_mask is not None:
            session_spec.set_t1_brain_mask(t1_brain_mask)

        session_spec.set_templates(*t1_study_template, *t2_study_template,
                multi_template_dir, multi_masking_dir)

        if no_crop:
            session_spec.turn_off_cropping()

        if mc_frame is not None:
            session_spec.set_mc_frame(mc_frame)

        # create pipelines
        order = []

        # Create pipeline.
        if run_anat:
            pre = PreFreeSurfer(session_spec)
            free = FreeSurfer(session_spec)
            post = PostFreeSurfer(session_spec)
            order += [pre, free, post]
        if run_func:
            vol = FMRIVolume(session_spec)
            surf = FMRISurface(session_spec)
            boldproc = DCANBOLDProcessing(session_spec)
            order += [vol, surf, boldproc]
        if run_summary:
            execsum = ExecutiveSummary(session_spec)
            order += [execsum]

        # Add optional pipeline stages
        if cleaning_json:
            cclean = CustomClean(session_spec, cleaning_json)
            order.append(cclean)

        if file_mapper_json:
            fmap = FileMapper(session_spec, file_mapper_json)
            order.append(fmap)

        # Special runtime options
        if stages:
            # User can indicate start or end or both; default
            # to entire list built above.
            start_idx = 0
            end_idx = len(order)

            idx_colon = stages.find(":")
            if idx_colon > -1:
                # Start stage is everything before the colon.
                start_stage = stages[:idx_colon]
                # End stage is everything after the colon.
                end_stage = stages[(idx_colon+1):]
            else:
                # No colon means no end stage.
                start_stage = stages
                end_stage = None

            names = [x.__class__.__name__ for x in order]

            if start_stage:
                assert start_stage in names, \
                        '"%s" is unknown, check class name and case for given stage' \
                        % start_stage
                start_idx = names.index(start_stage)

            if end_stage is not None:
                assert end_stage in names, \
                        '"%s" is unknown, check class name and case for given stage' \
                        % end_stage
                end_idx = names.index(end_stage)
                end_idx += 1 # Include end stage.

            # Slice the list.
            order = order[start_idx:end_idx]

        if check_only:
            for stage in order:
                print('checking outputs for %s' % stage.__class__.__name__, flush=True)
                try:
                    stage.check_expected_outputs()
                except AssertionError:
                    pass
            return
        if print_commands:
            for stage in order:
                stage.deactivate_runtime_calls()
                stage.deactivate_check_expected_outputs()
                stage.deactivate_remove_expected_outputs()
        if ignore_expected_outputs:
            print('ignoring checks for expected outputs.', flush=True)
            for stage in order:
                stage.activate_ignore_expected_outputs()

        # run pipelines
        for stage in order:
            print('running %s' % stage.__class__.__name__, flush=True)
            print(stage, flush=True)
            stage.run(ncpus)


if __name__ == '__main__':
    _cli()

