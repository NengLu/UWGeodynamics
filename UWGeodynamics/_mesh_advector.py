from copy import copy
import underworld as uw
import numpy as np
import sys
from mpi4py import MPI

comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()


class _mesh_advector(object):

    def __init__(self, Model, axis):

        self._mesh2nd = copy(Model.mesh)
        self.Model = Model
        self.axis = axis

    def advect_mesh(self, dt):

        axis = self.axis

        if axis != 0:
            raise ValueError("Axis not supported yet")

        # Get minimum and maximum coordinates for the current mesh
        minX, maxX = self._get_minmax_coordinates_mesh(axis)

        minvxLeftWall, maxvxLeftWall   = self._get_minmax_velocity_wall(self.Model._left_wall, axis)
        minvxRightWall, maxvxRightWall = self._get_minmax_velocity_wall(self.Model._right_wall, axis)

        if np.abs(maxvxRightWall) > np.abs(minvxRightWall):
            vxRight = maxvxRightWall
        else:
            vxRight = minvxRightWall

        if (np.abs(maxvxLeftWall)  > np.abs(minvxLeftWall)):
            vxLeft = maxvxLeftWall
        else:
            vxLeft = minvxLeftWall

        minX += vxLeft * dt
        maxX += vxRight * dt
        length = np.abs(minX - maxX)

        if self.Model.mesh.dim <3:
            newValues = np.linspace(minX, maxX, self.Model.mesh.elementRes[axis]+1)
            newValues = np.repeat(newValues[np.newaxis,:], self.Model.mesh.elementRes[1] + 1, axis)
        else:
            newValues = np.linspace(minX, maxX, self.Model.mesh.elementRes[axis]+1)
            newValues = np.repeat(newValues[np.newaxis, :], self.Model.mesh.elementRes[1] + 1, axis)
            newValues = np.repeat(newValues[np.newaxis, :, :], self.Model.mesh.elementRes[2] + 1, axis)

        with self._mesh2nd.deform_mesh():
            values = newValues.flatten()
            self._mesh2nd.data[:, axis] = values[self._mesh2nd.data_nodegId.ravel()]

        uw.barrier()

        with self.Model.mesh.deform_mesh():
            self.Model.mesh.data[:, axis] = self._mesh2nd.data[:, axis]

        self.Model.velocityField.data[...] = np.copy(self.Model.velocityField.evaluate(self.Model.mesh))
        self.Model.pressureField.data[...] = np.copy(self.Model.pressureField.evaluate(self.Model.mesh.subMesh))

        if self.Model._right_wall.data.size > 0:
            self.Model.velocityField.data[self.Model._right_wall.data, axis] = vxRight

        if self.Model._left_wall.data.size > 0:
            self.Model.velocityField.data[self.Model._left_wall.data, axis]  = vxLeft

    def _get_minmax_velocity_wall(self, wall, axis=0):
        """ Return the minimum and maximum velocity component on the wall

        parameters:
        -----------
            wall: (indexSet)
                The wall.
            axis:
                axis (velocity component).
        """

        # Initialise value to max and min sys values
        maxV = np.ones((1)) * sys.float_info.min
        minV = np.ones((1)) * sys.float_info.max


        # if local domain has wall, get velocities
        if wall.data.size > 0:
            velocities  = self.Model.velocityField.data[wall.data, axis]
            # get local min and max
            maxV[0] = velocities.max()
            minV[0] = velocities.min()

        # reduce operation
        uw.barrier()
        comm.Allreduce(MPI.IN_PLACE, maxV, op=MPI.MAX)
        comm.Allreduce(MPI.IN_PLACE, minV, op=MPI.MIN)
        uw.barrier()

        return minV, maxV

    def _get_minmax_coordinates_mesh(self, axis=0):
        """ Return the minimum and maximum coordinates along axis

        parameter:
        ----------
            axis:
                axis

        returns:
        -------
            tuple: minV, maxV

        """
        maxVal = np.zeros((1))
        minVal = np.zeros((1))
        maxVal[0] = self.Model.mesh.data[:, axis].max()
        minVal[0] = self.Model.mesh.data[:, axis].min()

        uw.barrier()
        comm.Allreduce(MPI.IN_PLACE, maxVal, op=MPI.MAX)
        comm.Allreduce(MPI.IN_PLACE, minVal, op=MPI.MIN)
        uw.barrier()

        return minVal, maxVal


