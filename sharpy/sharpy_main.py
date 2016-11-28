import sharpy.utils.solver_interface as solver_interface
import sharpy.utils.input_arg as input_arg

# solver list -- It is important to import them here
from presharpy.problemdata import ProblemData
from sharpy.beam.solver.nonlinearstatic import NonLinearStatic
# ------------

solver_interface.print_available_solvers()
settings = input_arg.read_settings()

# Loop for the solvers specified in *.solver.txt['SHARPy']['flow']
# run preSHARPy
data = ProblemData(settings)
for solver_name in settings['SHARPy']['flow']:
    print('Generating an instance of %s' % solver_name)
    cls_type = solver_interface.solver_from_string(solver_name)
    solver = cls_type()
    solver.initialise(data)
    data = solver.run()

data.plot_configuration(plot_grid=False)
