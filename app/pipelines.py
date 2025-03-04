import inspect
import json
import multiprocessing as mp
import subprocess

import os

from helpers import (get_fmriname, get_readoutdir, get_realdwelltime,
                     get_relpath, get_taskname, ijk_to_xyz, get_TR)


class ParameterSettings(object):
    """
    Paths to files and settings required to run DCAN HCP.  Class attributes
    should be any parameters which are independent of input image parameters,
    for example, the target atlases. Instance attributes are attributes which
    are read from or dependent upon inputs.  Additionally, they may include
    special options for processing or for overriding class attributes.  All
    attributes will be formatted according to the available
    """

    summary_dir = "summary_{DCANBOLDPROCVER}"

    # @ templates @ #
    # MNI0.7mm template
    t1template = "{HCPPIPEDIR_Templates}/INFANT_MNI_T1_1mm.nii.gz"
    # Brain extracted MNI0.7mm template
    t1templatebrain = "{HCPPIPEDIR_Templates}/INFANT_MNI_T1_1mm_brain.nii.gz"
    # MNI2mm template
    t1template2mm = "{HCPPIPEDIR_Templates}/INFANT_MNI_T1_2mm.nii.gz"
    # MNI0.7mm T2wTemplate
    t2template = "{HCPPIPEDIR_Templates}/INFANT_MNI_T2_1mm.nii.gz"
    # Brain extracted MNI0.7mm T2wTemplate
    t2templatebrain = "{HCPPIPEDIR_Templates}/INFANT_MNI_T2_1mm_brain.nii.gz"
    # MNI2mm T2wTemplate
    t2template2mm = "{HCPPIPEDIR_Templates}/INFANT_MNI_T2_2mm.nii.gz"
    # Brain mask MNI0.7mm template
    templatemask = "{HCPPIPEDIR_Templates}/INFANT_MNI_T1_1mm_brain_mask.nii.gz"
    # MNI2mm template
    template2mmmask = "{HCPPIPEDIR_Templates}/INFANT_MNI_T1_2mm_brain_mask_dil" \
                      ".nii.gz"
    # Myelin Maps
    refmyelinmaps = "{HCPPIPEDIR_Templates}/standard_mesh_atlases/" \
                    "Conte69.MyelinMap_BC.164k_fs_LR.dscalar.nii"
    # Surface Atlas Templates
    surfatlasdir = "{HCPPIPEDIR_Templates}/standard_mesh_atlases"
    # Grayordinate Templates
    grayordinatesdir = "{HCPPIPEDIR_Templates}/91282_Greyordinates"

    # PreFreeSurfer templates used in masking and segmentation for infants
    multitemplatedir = "{HCPPIPEDIR_Templates}/JLF_templates"      # brains for new method.
    multimaskingdir = "{HCPPIPEDIR_Templates}/DCAN_neo_JLF_heads"  # heads for old method (new method has no heads).
    t2wstudytemplate="{HCPPIPEDIR_Templates}/temp_nih_T2w_atl.nii.gz"
    t2wstudytemplatebrain="{HCPPIPEDIR_Templates}/temp_nih_T2w_atl_brain.nii.gz"
    templatesidentifier="{HCPPIPEDIR_Templates}/README.txt"

    # FreeSurfer file used for infants.
    gca = "{FREESURFER_HOME}/average/RB_all_2008-03-26.gca"

    # @ various settings @ #
    # fov size for robust_fov automatic cropping
    brainsize = 120
    # final time series isotropic resolution (mm)
    fmrires = 2.0
    # resolution of greyordinates (mm)
    grayordinatesres = 2
    # smoothing sigma for final greyordinate data (mm)
    smoothingFWHM = 2
    # surface registration algorithm, one of: FS, MSMSulc
    regname = "FS"
    # number of vertices (in thousands) for high and low res surface meshes
    hiresmesh = "164"
    lowresmesh = "32"
    # motion correction method
    mctype = 'MCFLIRT'

    # @ configuration files @ #
    topupconfig = "{HCPPIPEDIR_Config}/b02b0.cnf"
    fnirtconfig = "{HCPPIPEDIR_Config}/T1_2_MNI152_2mm.cnf"
    freesurferlabels = "{HCPPIPEDIR_Config}/FreeSurferAllLut.txt"
    subcortgraylabels = "{HCPPIPEDIR_Config}/FreeSurferSubcortical" \
                            "LabelTableLut.txt"

    # @ bold processing defaults @ #
    # brain radius of infant subject set.
    brain_radius = 45
    # threshold for valid signal regression frames.
    fd_threshold = 0.3
    # bold signal temporal bandpass filter parameters
    filter_order = 2
    lower_bpf = 0.009
    upper_bpf = 0.080
    # motion regressor bandstop filter parameters
    motion_filter_type = 'notch'
    motion_filter_order = 4
    band_stop_min = None
    band_stop_max = None
    motion_filter_option = 5
    # seconds to omit from beginning of scan
    skip_seconds = 5
    # cont frames
    contiguous_frames = 5

    # Method to be used for JLF.
    jlf_method = "T1W"

    # Values for FreeSurfer:
    max_cortical_thickness = 5
    smoothing_iterations = 10
    # aseg file
    aseg = "DEFAULT"

    subcortical_map_method = "ROI_MAP"

    t1_brain_mask = None

    # Values for FMRIVolume:
    mc_frame = 17

    def __init__(self, bids_data, output_directory):
        """
        Specification to run pipeline on a single subject session.
        :param bids_data: yielded spec from read_bids_dataset
        :param output_directory: output directory for pipeline
        """

        # input bids data struct
        self.bids_data = bids_data
        # @ parameters read from bids @ #
        self.t1w = self.bids_data['t1w']
        self.t1samplespacing = get_realdwelltime(
            self.bids_data['t1w_metadata'])

        if 'T2w' in self.bids_data['types']:
            self.useT2 = 'true'
            self.t2w = self.bids_data['t2w']
            self.t2samplespacing = get_realdwelltime(
                self.bids_data['t2w_metadata'])
        else:
            # The infant pipeline does not work without T2w...
            print('\nERROR: The infant pipeline is not able to run without T2w data.\n')
            raise Exception('The infant pipeline is not able to run without T2w data')
            # ...but if it ever does, do this.
            self.useT2 = 'false'
            self.t2w = []
            self.t2samplespacing = None


        # distortion correction method: TOPUP, FIELDMAP, or NONE, inferred
        # from files, defaults to spin echo (topup) if both field maps exist
        self.unwarpdir = get_readoutdir(self.bids_data['t1w_metadata'])
        fmap_types = {'magnitude', 'magnitude1', 'magnitude2', 'phasediff',
                'phase1', 'phase2', 'fieldmap'}
        if 'epi' in self.bids_data['types']:
            self.dcmethod = 'TOPUP'
            # spin echo field map spacing @TODO read during volume per fmap?
            self.echospacing = self.bids_data['fmap_metadata']['positive'][0][
                'EffectiveEchoSpacing']
            self.echospacing = ('%.12f' % self.echospacing).rstrip('0')
            # distortion correction phase encoding direction
            self.seunwarpdir = ijk_to_xyz(
                self.bids_data['func_metadata'][0]['PhaseEncodingDirection'])

            # set unused fmap parameters to none
            self.fmapmag = self.fmapphase = self.fmapgeneralelectric = \
                self.echodiff = self.gdcoeffs = None
            # @TODO decide on bfcmethod for fmri data.

        elif fmap_types.intersection(set(self.bids_data['types'])):
            self.dcmethod = 'FIELDMAP'
            types = self.bids_data['fmap'].keys()
            # gradient field map delta TE
            if 'magnitude1' in types and 'magnitude2' in types:
                self.fmapmag = self.bids_data['fmap']['magnitude1']
                self.echodiff = self.bids_data['fmap_metadata'][
                        'magnitude2']['EchoTime'] - self.bids_data[
                        'fmap_metadata']['magnitude1']['EchoTime']
                self.echodiff = '%g' % (self.echodiff * 1000.)  # milliseconds
                self.fmapgeneralelectric = None
            elif 'magnitude' in types:
                raise NotImplementedError
            else:
                raise Exception('No FM magnitude image identified')

            if 'phasediff' in types:
                self.fmapphase = self.bids_data['fmap']['phasediff']
            elif 'phase1' in types and 'phase2' in types:
                raise NotImplementedError
            else:
                raise Exception('No FM phase image identified')

            # set unused spin echo parameters to none
            self.seunwarpdir = self.gdcoeffs = self.echospacing = None

        else:
            # all distortion correction parameters set to none
            self.fmapmag = self.fmapphase = self.fmapgeneralelectric = \
                self.echodiff = self.gdcoeffs = self.dcmethod = \
                self.seunwarpdir = self.echospacing = None

        if not hasattr(self, 'fmribfcmethod'):
            self.fmribfcmethod = None

        # @TODO handle bids formatted physio data
        self.physio = None

        # intermediate template defaults
        self.t1wstudytemplate = None
        self.t1wstudytemplatebrain = None

        # @ output files @ #
        self.path = os.path.join(output_directory, 'files')
        self.logs = os.path.join(output_directory, 'logs')
        self.subject = self.bids_data['subject']
        self.session = self.bids_data['session']

        # @ input files @ #
        session_root = '/'.join(self.t1w[0].split('/')[:-2])
        self.unproc = os.path.join(session_root, 'func')

        bids_input_root = '/'.join(session_root.split('/')[:-2])
        self.sourcedata_root = os.path.join(bids_input_root,'sourcedata')

        # print command for HCP
        self.printcom = ''

        # Default action for the Atropos mask-refinement step.
        self.atropos_mask_method = 'REFINE'

        # Default when doing alignment in PreFreeSurfer is to crop neck,
        # shoulders.
        self.crop = True


    def __getitem__(self, item):
        return self._params()[item]

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def _params(self):
        """
        gets all class parameters which do not start with an underscore.
        :return: dictionary of class parameter names and values.
        """
        params = inspect.getmembers(self, lambda a: not inspect.isroutine(a))
        params = {x[0]: x[1] for x in params if not x[0].startswith('_')}
        return params

    def _format(self):
        """
        formats all class parameter strings to insert environment variables.
        :return: None
        """
        params = self._params()
        # format all attributes
        for item, value in params.items():
            if isinstance(value, str):
                setattr(self, item, value.format(**os.environ))

    def get_params(self):
        """
        formats and returns instance variables.
        :return: dictionary of instance variable names and values
        """
        self._format()
        return self._params()

    def get_bids(self, *args):
        """
        get data from bids struct
        :param args: list of nested dict keys, e.g. one must provide 'fmap',
        'positive' to retrieve the positive spin echo field maps.
        :return: bids data
        """
        val = self.bids_data
        for arg in args:
            val = val[arg]
        return val

    def set_anat_only(self, anat_only=False):
        if anat_only:
            # Assume there is no 'func' data...
            self.unproc = None
            # and no output from dcan-bold-proc.
            self.summary_dir = None

    def set_atropos_mask_method(self, value):
        self.atropos_mask_method = value

    def set_bandstop_filter(self, lower_bound, upper_bound,
                            filter_type='notch'):
        self.motion_filter_type = filter_type
        self.band_stop_min = lower_bound
        self.band_stop_max = upper_bound

    def set_hypernormalization_method(self, norm_method):
        self.norm_method = norm_method

    def set_mc_frame(self, value):
        self.mc_frame = value

    def set_templates(self, t1_study_template, t1_study_template_brain, t2_study_template,
            t2_study_template_brain, multi_template_dir, multi_masking_dir):
        """
        set templates for intermediate registration steps.
        :param t1_study_template: intermediate registration template head.
        :param t1_study_template_brain: intermediate registration template brain.
        :param t2_study_template: intermediate registration template head.
        :param t2_study_template_brain: intermediate registration template brain.
        :param multi_template_dir: directory of templates for JLF.
        :param multi_masking_dir: directory of masks for JLF.
        :return: None
        """
        if t1_study_template:
            self.t1wstudytemplate = t1_study_template
            self.t1wstudytemplatebrain = t1_study_template_brain

        if t2_study_template:
            self.t2wstudytemplate = t2_study_template
            self.t2wstudytemplatebrain = t2_study_template_brain

        if multi_template_dir:
            self.multitemplatedir = multi_template_dir

        if multi_masking_dir:
            self.multimaskingdir = multi_masking_dir

    def turn_off_cropping(self):
        self.crop = False

    def set_dcmethod(self, value):
        if value:
            self.dcmethod = value

    def set_atropos_range(self, lower_bound, upper_bound):
        # Set the values to send to PreFreeSurfer.
        self['atropos_label_min'] = lower_bound
        self['atropos_label_max'] = upper_bound


    def set_max_cortical_thickness(self, value):
        # Set the value to send to FreeSurfer.
        if value:
            self.max_cortical_thickness = value
        else:
            self.max_cortical_thickness = 5  # FreeSurfer default is 5 mm.


    def set_jlf_method(self, value):
        if value and value is not None:
            self.jlf_method = value
        else:
            # Default method:
            self.jlf_method = "T1W"

    def set_smoothing_iterations(self, value):
        if value:
            self.smoothing_iterations = value
        else:
            self.smoothing_iterations = 10 # FreeSurfer default.

    def set_subcortical_map_method(self, value):
        if value and value is not None:
            self.subcortical_map_method = value
        else:
            self.subcortical_map_method = "ROI_MAP"

    def set_t1_brain_mask(self, value):
        # The brain mask is generated by PreFreeSurfer. This allows the user
        # to pass in a different brain mask to be used.
        if value:
            self.t1_brain_mask = value


    def set_aseg(self, value):
        # aseg is generated by PreFreeSurfer, but if user wants to pass
        # a different aseg to FreeSurfer, this allows that to happen.
        if value:
            # Set to the path provided.
            self.aseg = value
        else:
            # Will make the correct path when FreeSurfer is initialized.
            self.aseg = "DEFAULT"


class Status(object):
    """Status provides and updates node status information.

    Status information for each node is stored in the
    processing_logs/NodeName/status.json file.  This class provides an
    abstraction layer between the NodeStep class and this status file.

    This is a write through data structure
    """
    name = 'status.json'
    states = {
        'unchecked': 999,
        'not_started': 4,
        'failed': 3,
        'incomplete': 2,
        'succeeded': 1,
    }

    def __init__(self, folder_path):
        """
        Args:
            folder_path (str): absolute path to the Stage's bookkeeping
            (e.g. /output/sub/ses/processing_logs/PipelineStage)
        """
        self.file_path = os.path.join(folder_path, Status.name)

        defaults = {
            'num_runs': 0,
            'node_status': Status.states['not_started'],
            'comment': '',
            }

        if not os.path.exists(self.file_path):
            self._write_dict(**defaults)

    def __getitem__(self, key):
        with open(self.file_path, 'r') as fd:
            return json.load(fd)[key]

    def __setitem__(self, key, value):
        with open(self.file_path, 'r') as fd:
            store = json.load(fd)
        store[key] = value
        self._write_dict(**store)
        return value

    def _write_dict(self, **contents):
        with open(self.file_path, 'w') as fd:
            json.dump(contents, fd, indent=4)

    def increment_run(self):
        self['num_runs'] += 1

    def update_start_run(self):
        self.increment_run()
        self['node_status'] = Status.states['incomplete']

    def update_success(self):
        self['node_status'] = Status.states['succeeded']
        self['comment'] = ''

    def update_failure(self, comment=''):
        self['node_status'] = Status.states['failed']
        self['comment'] = comment

    def update_unchecked(self, comment='no expected_outputs list for '
                                       'completed node'):
        self['node_status'] = Status.states['unchecked']
        self['comment'] = comment

    def succeeded(self):
        return self['node_status'] in (Status.states['succeeded'],
                                       Status.states['unchecked'])


class Stage(object):
    """
    Base abstract class for pipeline stages.

    attributes:
    config: ParameterSettings object.
    kwargs: dict of attributes returned from ParamterSettings object.

    abstract methods which require overriding:
    script: script / tool / executable to run as a subprocess.
    args:  should provide command line arguments to the script.  Usually
    utilizes a "spec" attribute which is then formatted with the "kwargs"
    attribute.  See PreFreeSurfer.  Must be a generator for concurrency.  See
    FMRIVolume.

    optional overriding:
    cmdline:  will need overriding as generator to utilize concurrency.  See
    FMRIVolume.
    setup: executes prior to executable.  Recommended to wrap super().
    teardown: executes after executable completes.  Recommended to wrap super().

    run: not intended for override.
    """

    # runtime settings
    call_active = True
    check_expected_outputs_active = True
    remove_expected_outputs_active = True
    ignore_expected_outputs = False

    def __init__(self, config):
        self.config = config
        self.kwargs = config.get_params()
        self.status = Status(self._get_log_dir())
        here = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(here, 'pipeline_expected_outputs.json')) as fd:
            jso = json.load(fd)
            self.expected_outputs_spec = jso[self.__class__.__name__]

    def __str__(self):
        cmdline = self.cmdline()
        if inspect.isgenerator(cmdline):
            string = ''
            for cmd in cmdline:
                string += ' \\\n    '.join(cmd.split()) + '\n'
        else:
            string = ' \\\n    '.join(cmdline.split())
        return string

    @classmethod
    def deactivate_runtime_calls(cls):
        """
        prevents Stage(s) from executing subprocesses
        """
        cls.call_active = False

    @classmethod
    def deactivate_check_expected_outputs(cls):
        cls.check_expected_outputs_active = False

    @classmethod
    def deactivate_remove_expected_outputs(cls):
        cls.remove_expected_outputs_active = False

    @classmethod
    def activate_ignore_expected_outputs(cls):
        cls.ignore_expected_outputs = True

    def _get_log_dir(self):
        """
        returns the subject's log directory for this stage
        :return: path to log directory
        """
        log_dir = os.path.join(self.kwargs['logs'], self.__class__.__name__)
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        return log_dir

    def check_expected_outputs(self):
        """
        checks the existence of the expected outputs for this stage.
        :return: True if all outputs exist, else False.
        """
        if not self.check_expected_outputs_active:
            return True

        outputs = self.get_expected_outputs()
        checklist = [os.path.exists(p) for p in outputs]
        if not all(checklist):
            print('missing expected outputs from %s' %
                  self.__class__.__name__)
            dne_list = [f for i, f in enumerate(outputs) if not checklist[i]]
            for f in dne_list:
                print('file not found: %s' % f)
            if not self.ignore_expected_outputs:
                return False

        return True

    def get_expected_outputs(self):
        """
        formats and returns expected outputs.  Must be overridden for
        expected outputs of concurrent executions.
        :return: formatted list of expected outputs
        """
        expected_outputs = [p.format(**self.kwargs)
                            for p in self.expected_outputs_spec]
        expected_outputs += self.get_conditional_expected_outputs()
        return expected_outputs

    def get_conditional_expected_outputs(self):
        """
        this method includes any logic which needs to be used to determine
        if a file is an expected output, for example when different input
        modalities are utilized.  Override this for individual stages to
        have contextually defined expected outputs.
        :return: list of any conditional expected outputs
        """
        return []

    def remove_expected_outputs(self):
        """
        removes expected outputs for this stage if they exist.
        :return: None
        """
        if not self.remove_expected_outputs:
            return
        outputs = self.get_expected_outputs()
        checklist = [os.path.isfile(p) for p in outputs]
        if any(checklist):
            print('found outputs from an earlier run of %s' %
                  self.__class__.__name__)
            rm_list = [f for i, f in enumerate(outputs) if checklist[i]]
            for f in rm_list:
                print('removing %s' % f)
                os.remove(f)

    def identify_templates(self):
        """
        run prior to each stage to identify the actual folder from which the
        templates came.
        """
        # Identify which templates will be used.
        if os.path.isfile(self.config.templatesidentifier):
            print("Templates information follows:")
            with open(self.config.templatesidentifier) as rm:
                rmcontent =  rm.readlines()
                for rmline in rmcontent:
                    print("\t%s" % rmline.strip(), flush=True)
                rm.close()
        else:
            print("There is no available information about the templates being used.", flush=True)


    def setup(self):
        """
        runs prior to main script for this stage.
        :return: None
        """
        self.status.update_start_run()
        self.remove_expected_outputs()

    def teardown(self, result=0):
        """
        runs following the main script for this stage
        :param result: exit status or list of exit statuses for the main
        script.
        :return: None
        """
        if isinstance(result, list) and all(v == 0 for v in result):
            result = 0
        if result == 0:
            self.status.update_success()
        else:
            self.status.update_failure(
                'stage terminated with exit code %s' % result
            )
        if not self.check_expected_outputs():
            self.status.update_failure(
                'stage terminated, some required files were not created.'
            )
        # @TODO update status in case of missing expected outputs
        # finally, terminate pipeline in case of failure.
        if self.status['node_status'] != Status.states['succeeded']:
            raise Exception('error caught during stage: %s' %
                            self.__class__.__name__)

    @property
    def args(self):
        """
        Formats the command line argument "spec", returning the full string of
        inputs to the main script.  Must be overridden.
        :return: string of space separated command line arguments.
        """
        raise NotImplementedError

    @property
    def script(self):
        """
        formattable string for the path to the main script.  Must be
        overridden.
        """
        raise NotImplementedError

    def cmdline(self):
        """
        returns the formatted string for the command to be called.  Must
        be overridden as a generator object for concurrent execution.
        :return: command line string.
        """
        script = self.script.format(**os.environ)
        return ' '.join((script, self.args))

    def run(self, ncpus=1):
        """
        runs this stage
        :param ncpus: number of available cores for concurrent execution or
        for multithreaded computation.
        :return: None
        """
        self.identify_templates()
        self.setup()
        # a generator cmdline supports parallel execution
        if inspect.isgeneratorfunction(self.cmdline):
            cmdlist = []
            for cmd in self.cmdline():
                log_dir = self._get_log_dir()
                out_log = os.path.join(log_dir,
                                       self.kwargs['fmriname'] + '.out')
                err_log = os.path.join(log_dir,
                                       self.kwargs['fmriname'] + '.err')
                cmdlist.append((cmd, out_log, err_log))
            # This path is used when we are in stages that make a thread for
            # each task. Cap the number of processes as we keep running out of
            # memory when we have too many tasks - KJS 20200303
            if ncpus > 6:
                ncpus=6
            with mp.Pool(processes=ncpus) as pool:
                result = pool.starmap(self.call, cmdlist)
        else:
            cmd = self.cmdline()
            log_dir = self._get_log_dir()
            out_log = os.path.join(log_dir, self.__class__.__name__ + '.out')
            err_log = os.path.join(log_dir, self.__class__.__name__ + '.err')
            result = self.call(cmd, out_log, err_log, num_threads=ncpus)
        self.teardown(result)

    def call(self, *args, **kwargs):
        """
        runs command if call is active.
        """
        if self.call_active:
            return _call(*args, **kwargs)
        else:
            return 0  # "success"


class PreFreeSurfer(Stage):

    script = '{HCPPIPEDIR}/PreFreeSurfer/PreFreeSurferPipeline.sh'

    spec = ' --path={path}' \
           ' --t1={t1}' \
           ' --t2={t2}' \
           ' --t1template={t1template}' \
           ' --t1templatebrain={t1templatebrain}' \
           ' --t1template2mm={t1template2mm}' \
           ' --t2template={t2template}' \
           ' --t2templatebrain={t2templatebrain}' \
           ' --t2template2mm={t2template2mm}' \
           ' --templatemask={templatemask}' \
           ' --template2mmmask={template2mmmask}' \
           ' --brainsize={brainsize}' \
           ' --fnirtconfig={fnirtconfig}' \
           ' --fmapmag={fmapmag}' \
           ' --fmapphase={fmapphase}' \
           ' --fmapgeneralelectric={fmapgeneralelectric}' \
           ' --echodiff={echodiff}' \
           ' --SEPhaseNeg={sephaseneg}' \
           ' --SEPhasePos={sephasepos}' \
           ' --echospacing={echospacing}' \
           ' --seunwarpdir={seunwarpdir}' \
           ' --t1samplespacing={t1samplespacing}' \
           ' --t2samplespacing={t2samplespacing}' \
           ' --unwarpdir={unwarpdir}' \
           ' --gdcoeffs={gdcoeffs}' \
           ' --avgrdcmethod={dcmethod}' \
           ' --topupconfig={topupconfig}' \
           ' --useT2={useT2}' \
           ' --t1n={normalization}' \
           ' --printcom={printcom}' \
           ' --multitemplatedir={multitemplatedir}' \
           ' --multimaskingdir={multimaskingdir}' \
           ' --t1studytemplate={t1wstudytemplate}' \
           ' --t1studytemplatebrain={t1wstudytemplatebrain}' \
           ' --t2studytemplate={t2wstudytemplate}' \
           ' --t2studytemplatebrain={t2wstudytemplatebrain}' \
           ' --atroposmaskmethod={atropos_mask_method}' \
           ' --atroposlabelmin={atropos_label_min}' \
           ' --atroposlabelmax={atropos_label_max}' \
           ' --jlfmethod={jlf_method}' \
           ' --t1brainmask={t1_brain_mask}' \
           ' --crop={crop}'


    def __init__(self, config):
        super(__class__, self).__init__(config)
        # modify t1/t2 inputs for spec
        self.kwargs['t1'] = '@'.join(self.kwargs.get('t1w'))
        self.kwargs['t2'] = '@'.join(self.kwargs.get('t2w', []))
        if self.kwargs['dcmethod'] == 'TOPUP':
            self.kwargs['sephasepos'], self.kwargs['sephaseneg'] = \
                self._get_intended_sefmaps()
        else:
            self.kwargs['sephasepos'] = None
            self.kwargs['sephaseneg'] = None
        self.kwargs['normalization'] = 'true'

    def _get_intended_sefmaps(self):
        """
        search for IntendedFor field from sidecar json, else give the first
        spin echo pair.  @TODO Unfortunately, it will cause problems if someone
        includes the substring "T1w" in a spin echo sidecar name.
        :return: pair of spin echos, parallel
        """

        intended_idx = {}
        for direction in ['positive', 'negative']:
            for idx, sefm in enumerate(self.config.get_bids('fmap_metadata',
                                                        direction)):
                intended_targets = sefm.get('IntendedFor', [])
                if 'T1w' in ' '.join(intended_targets):
                    intended_idx[direction] = idx
                    break
            else:
                if idx != 0:
                    print('WARNING: the intended %s spin echo for anatomical '
                          'distortion correction is not explicitly defined in '
                          'the sidecar json.' % direction)
                intended_idx[direction] = 0

        return self.config.get_bids('fmap', 'positive', intended_idx[
            'positive']), \
            self.config.get_bids('fmap', 'negative', intended_idx['negative'])

    @property
    def args(self):
        # None to NONE
        kw = {k: (v if v is not None else "NONE")
              for k, v in self.kwargs.items()}
        return self.spec.format(**kw)


class FreeSurfer(Stage):

# For infants we run FNL_FreeInfantPipeline.sh (not FreeSurferPipeline.sh).
    script = '{HCPPIPEDIR}/FreeSurfer/FNL_FreeInfantPipeline.sh'

    spec = ' --subject={subject}' \
           ' --subjectDIR={t1w_path}' \
           ' --t1={t1_restore}' \
           ' --t1brain={t1_restore_brain}' \
           ' --t2={t2_restore}' \
           ' --useT2={useT2}' \
           ' --aseg={aseg}' \
           ' --t1n={t1n_image}' \
           ' --t1nbrain={t1n_brain}' \
           ' --gca={gca}' \
           ' --maxThickness={max_cortical_thickness}' \
           ' --smoothingIterations={smoothing_iterations}' \
           ' --normalizationMethod={norm_method}' \
           ' --printcom={printcom}'

    def __init__(self, config):
        super(__class__, self).__init__(config)
        # Note: 'subjectDIR' in script is actually path to T1w (files produced by PreFreeSurfer).
        self.kwargs['t1w_path'] = os.path.join(
            self.kwargs['path'], 'T1w')
        self.kwargs['t1_restore'] = os.path.join(
            self.kwargs['t1w_path'], 'T1w_acpc_dc_restore.nii.gz')
        self.kwargs['t1_restore_brain'] = os.path.join(
            self.kwargs['t1w_path'], 'T1w_acpc_dc_restore_brain.nii.gz')
        self.kwargs['t2_restore'] = os.path.join(
            self.kwargs['t1w_path'], 'T2w_acpc_dc_restore.nii.gz')
        # Additional files needed by infants pipeline:
        if config.aseg is "DEFAULT":
            self.kwargs['aseg'] = os.path.join(
                    self.kwargs['t1w_path'], 'aseg_acpc.nii.gz')
        else:
            self.kwargs['aseg'] = os.path.abspath(config.aseg)
        self.kwargs['t1n_image'] = os.path.join(
            self.kwargs['t1w_path'], 'T1wN_acpc.nii.gz')
        self.kwargs['t1n_brain'] = os.path.join(
            self.kwargs['t1w_path'], 'T1wN_acpc_brain.nii.gz')

    @property
    def args(self):
        return self.spec.format(**self.kwargs)


class PostFreeSurfer(Stage):

    script = '{HCPPIPEDIR}/PostFreeSurfer/PostFreeSurferPipeline.sh'

    spec = ' --path={path}' \
           ' --subject={subject}' \
           ' --surfatlasdir={surfatlasdir}' \
           ' --grayordinatesdir={grayordinatesdir}' \
           ' --grayordinatesres={grayordinatesres}' \
           ' --hiresmesh={hiresmesh}' \
           ' --lowresmesh={lowresmesh}' \
           ' --subcortgraylabels={subcortgraylabels}' \
           ' --freesurferlabels={freesurferlabels}' \
           ' --refmyelinmaps={refmyelinmaps}' \
           ' --regname={regname}' \
           ' --useT2={useT2}' \
           ' --printcom={printcom}'

    def __init__(self, config):
        super(__class__, self).__init__(config)

    @property
    def args(self):
        return self.spec.format(**self.kwargs)


class FMRIVolume(Stage):

    script = '{HCPPIPEDIR}/fMRIVolume/GenericfMRIVolumeProcessingPipeline.sh'

    spec = ' --path={path}' \
           ' --fmriname={fmriname}' \
           ' --fmritcs={fmritcs}' \
           ' --fmriscout={fmriscout}' \
           ' --SEPhaseNeg={sephaseneg}' \
           ' --SEPhasePos={sephasepos}' \
           ' --fmapmag={fmapmag}' \
           ' --fmapphase={fmapphase}' \
           ' --fmapgeneralelectric={fmapgeneralelectric}' \
           ' --echospacing={echospacing}' \
           ' --echodiff={echodiff}' \
           ' --unwarpdir={seunwarpdir}' \
           ' --fmrires={fmrires}' \
           ' --dcmethod={dcmethod}' \
           ' --gdcoeffs={gdcoeffs}' \
           ' --topupconfig={topupconfig}' \
           ' --printcom={printcom}' \
           ' --biascorrection={fmribfcmethod}' \
           ' --mctype={mctype}' \
           ' --mcframe={mc_frame}' \
           ' --useT2={useT2}'

    def __init__(self, config):
        super(__class__, self).__init__(config)

    def __str__(self):
        string = ''
        for cmd in self.cmdline():
            string += ' \\\n    '.join(cmd.split()) + '\n'
        return string

    def _get_intended_sefmaps(self):
        """
        search for IntendedFor field from sidecar json to determine
        appropriate field map pair, else give the first spin echo pair.
        :return: pair of spin echo filenames, positive then negative
        """
        intended_idx = {}
        for direction in ['positive', 'negative']:
            for idx, sefm in enumerate(self.config.get_bids('fmap_metadata',
                                                            direction)):
                intended_targets = sefm.get('IntendedFor', [])
                if get_relpath(self.kwargs['fmritcs']) in ' '.join(
                        intended_targets):
                    intended_idx[direction] = idx
                    break
            else:
                if idx != 0:
                    print('WARNING: the intended %s spin echo for anatomical '
                          'distortion correction is not explicitly defined in '
                          'the sidecar json.' % direction)
                intended_idx[direction] = 0

        return self.config.get_bids('fmap', 'positive', intended_idx[
            'positive']), \
               self.config.get_bids('fmap', 'negative',
                                    intended_idx['negative'])

    @property
    def args(self):
        for fmri, meta in zip(self.config.get_bids('func'),
                              self.config.get_bids('func_metadata')):
            # set ts parameters
            self.kwargs['fmritcs'] = fmri
            self.kwargs['fmriname'] = get_fmriname(fmri)
            self.kwargs['fmriscout'] = None  # not implemented
            if self.kwargs['dcmethod'] == 'TOPUP':
                self.kwargs['seunwarpdir'] = ijk_to_xyz(
                        meta['PhaseEncodingDirection'])
                self.kwargs['sephasepos'], self.kwargs['sephaseneg'] = \
                    self._get_intended_sefmaps()
            else:
                self.kwargs['sephasepos'] = self.kwargs['sephaseneg'] = None
            # None to NONE
            kw = {k: (v if v is not None else "NONE")
                  for k, v in self.kwargs.items()}
            yield self.spec.format(**kw)

    def cmdline(self):
        script = self.script.format(**os.environ)
        for argset in self.args:
            yield ' '.join((script, argset))


class FMRISurface(Stage):

    script = '{HCPPIPEDIR}/fMRISurface/GenericfMRISurfaceProcessingPipeline.sh'

    spec = ' --path={path}' \
           ' --subject={subject}' \
           ' --fmriname={fmriname}' \
           ' --lowresmesh={lowresmesh}' \
           ' --fmrires={fmrires}' \
           ' --smoothingFWHM={smoothingFWHM}' \
           ' --grayordinatesres={grayordinatesres}' \
           ' --regname={regname}' \
           ' --repetitiontime={TR}' \
           ' --subcorticalmapmethod={subcortical_map_method}'

    def __init__(self, config):
        super(__class__, self).__init__(config)

    def __str__(self):
        string = ''
        for cmd in self.cmdline():
            string += ' \\\n    '.join(cmd.split()) + '\n'
        return string

    @property
    def args(self):
        for fmri, meta in zip(self.config.get_bids('func'),
                              self.config.get_bids('func_metadata')):
            self.kwargs['fmriname'] = get_fmriname(fmri)
            self.kwargs['TR'] = get_TR(meta)
            yield self.spec.format(**self.kwargs)

    def cmdline(self):
        script = self.script.format(**os.environ)
        for argset in self.args:
            yield ' '.join((script, argset))


class DCANBOLDProcessing(Stage):

    script = '{DCANBOLDPROCDIR}/dcan_bold_proc.py'

    spec = ' --subject={subject}' \
           ' --output-folder={path}' \
           ' --task={fmriname}' \
           ' --fd-threshold={fd_threshold}' \
           ' --filter-order={filter_order}' \
           ' --lower-bpf={lower_bpf}' \
           ' --upper-bpf={upper_bpf}' \
           ' --motion-filter-type={motion_filter_type}' \
           ' --physio={physio}' \
           ' --motion-filter-option={motion_filter_option}' \
           ' --motion-filter-order={motion_filter_order}' \
           ' --band-stop-min={band_stop_min}' \
           ' --band-stop-max={band_stop_max}' \
           ' --brain-radius={brain_radius}' \
           ' --skip-seconds={skip_seconds}' \
           ' --contiguous-frames={contiguous_frames}'

    def __init__(self, config):
        super(__class__, self).__init__(config)

    def setup(self):
        """
        make ventricle and white matter masks.
        :return:
        """
        super(__class__, self).setup()
        script = self.script.format(**os.environ)
        args = self.spec.format(**self.kwargs)
        cmd = ' '.join((script, args))
        cmd += ' --setup'
        log_dir = self._get_log_dir()
        out_log = os.path.join(log_dir, self.__class__.__name__ + '_setup.out')
        err_log = os.path.join(log_dir, self.__class__.__name__ + '_setup.err')
        result = self.call(cmd, out_log, err_log)

    def teardown(self, result=0):
        """
        concatenate dtseries, parcellate, create grayplots.
        :param result:
        :return:
        """
        fmris = [get_fmriname(fmri) for fmri in self.config.get_bids('func')]
        fmrisets = list(set([get_taskname(fmri)
                              for fmri in self.config.get_bids('func')]))

        script = self.script.format(**os.environ)
        args = self.spec.format(**self.kwargs)
        cmd = ' '.join((script, args))
        cmd += ' --teardown'

        for fmriset in fmrisets:
            fmrilist = sorted([ fmri for fmri in fmris if fmriset in fmri ])
            cmd += ' --tasklist ' + ','.join(fmrilist)

        log_dir = self._get_log_dir()
        out_log = os.path.join(log_dir, self.__class__.__name__ + '_teardown.out')
        err_log = os.path.join(log_dir, self.__class__.__name__ + '_teardown.err')
        result = self.call(cmd, out_log, err_log)

        super(__class__, self).teardown(result)

    @property
    def args(self):
        for fmri in self.config.get_bids('func'):
            self.kwargs['fmriname'] = get_fmriname(fmri)
            yield self.spec.format(**self.kwargs)

    def cmdline(self):
        script = self.script.format(**os.environ)
        for argset in self.args:
            yield ' '.join((script, argset))


class ExecutiveSummary(Stage):

    script = '{EXECSUMDIR}/ExecutiveSummary.py'

    spec = ' --bids-input={unproc}' \
           ' --output-dir={path}' \
           ' --participant-label={subject}' \
           ' --session-id={session}' \
           ' --atlas={t1templatebrain}' \
           ' --dcan-summary={summary_dir} '

    def __init__(self, config):
        super(__class__, self).__init__(config)

    @property
    def args(self):
        # None to NONE
        kw = {k: (v if v is not None else "NONE")
              for k, v in self.kwargs.items()}
        return self.spec.format(**kw)


class CustomClean(Stage):

    script = '{CUSTOMCLEANDIR}/cleaning_script.py'

    spec = ' --dir={path}' \
           ' --json={input_json}'

    def __init__(self, config, input_json):
        super(__class__, self).__init__(config)
        self.kwargs['input_json'] = input_json

    @property
    def args(self):
        return self.spec.format(**self.kwargs)


class FileMapper(Stage):

    script = '{FILEMAPPERDIR}/BIDS_filemapper_wrapper.sh'

    spec = '{subject} ' \
           '{session} ' \
           '{path} ' \
           '{input_json} '

    def __init__(self, config, input_json):
        super(__class__, self).__init__(config)
        self.kwargs['input_json'] = input_json

    @property
    def args(self):
        return self.spec.format(**self.kwargs)


def _call(cmd, out_log, err_log, num_threads=1):
    env = os.environ.copy()
    if num_threads > 1:
        # set parallel environment variables
        env['OMP_NUM_THREADS'] = str(num_threads)
        env['ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS'] = str(2) # str(num_threads)
        if num_threads != 1:
            print('Keep ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS at 1 instead of %s.' % num_threads)
    with open(out_log, 'w') as out, open(err_log, 'w') as err:
        result = subprocess.call(cmd.split(), stdout=out, stderr=err, env=env)
        if type(result) is list:
            if all(v == 0 for v in result):
                result = 0
    return result

