
import csv
import math
import os
from .PlateExceptions import *
from collections import OrderedDict
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from .SampleListReader import *

### Horizontal plates
# position_string_list = [f'{c}{i+1}' for c in 'ABCDEFGH' for i in range(12)]

### Vertical plates
# position_string_list = [f'{c}{i+1}' for i in range(12) for c in 'ABCDEFGH']

row_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

class Position(object):

    def __init__(self, plate, idx):

        self.plate = plate
        self.index = idx
        return    
    
    @property
    def row(self):
        return row_letters.index(self.plate.position_string_list[self.index][:1])
    
    @property
    def column(self):
        return int(self.plate.position_string_list[self.index][1:]) - 1
    
    @property
    def label(self):
        return self.plate.position_string_list[self.index]
    
    @classmethod
    def from_string(cls, plate, instr):
        idx = plate.position_string_list.index(instr)
        return Position(plate, idx)
    
    @classmethod
    def from_rowcol(cls, plate, row, col):
        idx = plate.position_string_list.index(f'{row_letters[row]}{col + 1}')
        return Position(plate, idx)


class Sample(object):

    def __init__(self, project, name, number):
        
        self.project = project
        self.name = name
        self.number = number

        return
    

class Project(object):

    def __init__(self, name, color = None, num_samples = 0):

        self.name = name
        self.color = color
        
        self.samples = [Sample(project=self, name=f'Sample{i + 1}', number= i+1) for i in range(num_samples)]

        return
    
    @property
    def sample_count(self):
        return len(self.samples)
    
    def addSample(self, sample):
        self.samples.append(sample)
        if sample.number is None:
            sample.number = self.sample_count
        return
    
    #### THIS DOESN'T REMOVE IT FROM THE PLATE
    def removeSample(self, sample):
        for i,s in enumerate(self.samples):
            if s is sample:
                self.samples.pop(i)
        return

    @classmethod
    def createFromSampleList(cls, filename, color=None):
        proj = None
        reader = SampleListReader(filename)
        proj = Project(reader.project_name, color)
        for i, s in enumerate(reader.sample_ids):
            proj.addSample(Sample(proj, s, reader.sample_numbers[i]))

        return proj

color_list = ['red', 'orange', 'yellow', 'green', 'purple', 'cyan', 'magenta', 'brown']

class Plate(OrderedDict):

    def __init__(self, name, rows, columns, vertical=True):
        super().__init__()
        self.name = name
        self.rows = rows
        self.columns = columns
        self.vertical = vertical
        if self.vertical:
            self.position_string_list = [f'{c}{i+1}' for i in range(self.columns) for c in row_letters[:self.rows]]
        else:
            self.position_string_list = [f'{c}{i+1}' for c in row_letters[:self.rows] for i in range(self.columns)]
        self.data = {pos : None for pos in self.position_string_list}
        # self.projects = []
        return
    
    @property
    def projects(self):
        return (list(dict.fromkeys([s.project for s in self.getSamples()])))

    @property
    def number_of_wells(self):
        return (self.rows * self.columns)
    
    @property
    def positions(self):
        return [Position.from_string(self, pos) for pos in self.position_string_list]


    def __setitem__(self, key, value):
        if isinstance(key, Position):
            key = key.label
        if key not in self.data.keys():
            raise KeyError
        if value is not None and not isinstance(value, Sample):
            raise TypeError("Only samples or `None` can be assigned to plate wells")
        self.data[key] = value

    
    def __getitem__(self, key):
        if isinstance(key, Position):
            return self.data[key.label]
        else:
            return self.data[key]

    def getUsedWells(self):
        return [Position.from_string(self, key) for key in self.data.keys() if self.data[key] is not None]

    def getFreeWells(self):
        return [Position.from_string(self, key) for key in self.data.keys() if self.data[key] is None]

    def getSamples(self):
        return [sample for sample in self.data.values() if sample is not None]
    
    
    def removeProject(self, project):
        for i, p in enumerate(self.projects):
            if p is project:
                for s in [x for x in p.samples]:
                    self.removeSample(s)
                # self.projects.pop(i)
    
    def getSamplePositions(self, sample):
        if sample is not None and sample in self.getSamples():
            rv = [Position.from_string(self, k) for k,v in self.data.items() if v is sample]
        else:
            rv = [None]
        return rv
    

    ### Only removes from plate, not from the project
    def removeSample(self, sample):
        # if sample is not None and self[sample.position] is sample:
        #     self[sample.position] = None
        if sample is not None:
            for pos in self.getSamplePositions(sample):
                if pos is not None:
                    self[pos] = None
        return

    def addProject(self, project, start_pos, first_sample=0, last_sample=None):
        start = start_pos.index
        if last_sample is None or last_sample >= project.sample_count:
            last_sample = project.sample_count - 1
        count = last_sample + 1 - first_sample
        
        ###  Count wells from start and see if enough
        if not start + count <= self.number_of_wells:
            raise NotEnoughWellsException(project.sample_count, self.number_of_wells - start)
        wells = self.position_string_list[start:start + count]
        if all((self.data[well] == None for well in wells)):
            # self.projects.append(project)
            for well, sample in list(zip(wells, project.samples[first_sample:last_sample+1])):
                self[well] = sample
            ### sort projects in the order they appear on plate
            # self.projects.sort(key=lambda pr: pr.samples[0].position.index)
        else:
            not_free = [well for well in wells if self[well] != None][0]
            raise WellNotFreeException(not_free)

    ### Output one plate to CSV file writer already open
    @classmethod
    def outputCSV(cls, writer, plate):
        row = ['Index', 'Position', 'Project', 'Sample', 'Number', str(plate.rows), str(plate.columns), str(plate.vertical), plate.name]
        writer.writerow(row)
        idx = 0
        for (well, sample) in plate.data.items():
            row = [
                idx,
                well,
                sample.project.name if sample is not None else 'EMPTY',
                sample.name if sample is not None else 'EMPTY',
                sample.number if sample is not None else '-'
            ]
            writer.writerow(row)
            idx += 1
        return
    
    ### Save list of plates to csv file
    @classmethod
    def saveToFile(cls, filename, plates):
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            for plate in plates:
                Plate.outputCSV(writer, plate)            
        return
    
    ### load plate file and return list of plate objects
    @classmethod
    def loadFromFile(cls, filename):
        plates = []  
        # pcount = 0
        
        with open(filename, 'r') as file:
            reader = csv.reader(file)
            readList = list(reader)

            def getNRCV(line):
                n = line[8] if len(line)>8 else "Unnamed Plate"
                r = int(line[5])
                c = int(line[6])
                v = False if line[7] == 'False' else True
                return (n, r, c, v)
            
            all_projects = []
            n, r, c, v = getNRCV(readList[0])
            newPlate = Plate(n, r, c, v)
            plates.append(newPlate)

            for line in list(readList)[1:]:
                ### detect start of new plate
                if line[0] == 'Index':
                    # plates.append(newPlate)
                    n, r, c, v = getNRCV(line)
                    newPlate = Plate(n, r, c, v)
                    plates.append(newPlate)
                    continue
                position = line[1]
                proj_name = line[2]
                sample_name = line[3]
                ### Some plate files don't have the sample number
                sample_number = int(line[4]) if len(line) > 4 and line[4] != '-' else None
                if sample_name != 'EMPTY' and proj_name != 'EMPTY':
                    # if proj_name not in [p.name for p in newPlate.projects]:
                    #     proj = None
                    #     for p in all_projects:
                    #         if p.name == proj_name:
                    #             proj = p
                    #     if proj is None:
                    #         proj = Project(proj_name, color_list[pcount%len(color_list)])
                    #         all_projects.append(proj)
                    #     # newPlate.projects.append(proj)

                    #     pcount += 1
                    # else:
                    def findProject(name):
                        for project in {proj for plate in plates for proj in plate.projects}:
                            if project.name == name:
                                return project
                        return None

                    project = findProject(proj_name)
                    # for p in {x for y in plates for x in y.projects}:
                    #     if p.name == proj_name:
                    #         project = p
                    #         break
                    if project is None:
                        project = Project(proj_name, color_list[len({proj for plate in plates for proj in plate.projects})%len(color_list)])
                    sample = Sample(project, sample_name, sample_number)
                    project.addSample(sample)
                    newPlate[position] = sample
            # plates.append(newPlate)
                    
        return plates
    
    

    @classmethod
    def saveImage(cls, filename, plates):
        count = len(plates)
        total_width = A4[0] - 20
        total_height = A4[1] - 200


        platew = total_width if count == 1 else total_width * 0.66 if count == 2 else (total_width / 2) - 20
        plateh = platew * 8/12
        text_box_height = 60

        c = canvas.Canvas(filename, pagesize=A4)
        c.setFillColor('black')
        c.drawString(20, A4[1]-20, os.path.basename(filename))
        for i, plate in enumerate(plates):
            bottomx = 15
            if i > 1:
                bottomx = bottomx + platew + 10
            bottomy = A4[1] - 50 - plateh
            if i % 2:
                bottomy = bottomy - plateh - 25 - text_box_height

            Plate.drawPlate(c, plate, (bottomx, bottomy), plateh, platew)
            Plate.labelPlate(c, plate, (bottomx, bottomy-text_box_height), text_box_height, platew)

        c.save()

        return
    
    @classmethod
    def labelPlate(cls, canvas, plate, bottom_left, height, width):

        label_depth = 3
        text_size = height // label_depth
        canvas.setFont("Helvetica", text_size)

        label_x = bottom_left[0]
        label_y = bottom_left[1] + height - (text_size/2)

        count = len(plate.projects)
        cols = (count // label_depth)
        if (count % label_depth):
            cols += 1
        colw = width / cols

        def getWidestName():
            widest = 0
            for proj in plate.projects:
                length = canvas.stringWidth(proj.name) + 5
                if length > widest:
                    widest = length
            return widest
        
        while getWidestName() > colw or height < text_size * (label_depth + 1):
            text_size -= 1
            while height >= text_size * (label_depth + 2):
                label_depth += 1            
                cols = (count // label_depth)
                if (count % label_depth):
                    cols += 1
                colw = width / cols
            canvas.setFont("Helvetica", text_size)

        canvas.rect(bottom_left[0], bottom_left[1], width, height, fill=0)
        for i, proj in enumerate(plate.projects):
            if i % label_depth == 0:
                label_x = bottom_left[0] + ((i//label_depth) * colw) + 5
                label_y = bottom_left[1] + height - (text_size/2) 
            label_y -= text_size * 1.1
            canvas.setFillColor(proj.color)
            canvas.rect(label_x, label_y, canvas.stringWidth(proj.name), text_size, stroke=0, fill=1)
            canvas.setFillColor('black')
            canvas.drawString(label_x, label_y + (text_size * 0.2), proj.name)
            
        return

    @classmethod
    def drawPlate(cls, canvas, plate, bottom_left, height, width):

        ratio = plate.columns / plate.rows

        if height > (1/ratio) * width:
            height = math.floor((1/ratio) * width)

        canvas.setFont("Helvetica", 15)
        canvas.drawString(bottom_left[0], bottom_left[1] + 5, plate.name)
        canvas.rect(bottom_left[0], bottom_left[1], width, height, fill=0)
        inset_y = math.floor(height/10)
        well_size = math.floor((height - (2 * inset_y)) / (plate.rows))
        well_radius = math.floor(well_size * 0.45)
        inset_x = math.floor((width - ((plate.columns) * well_size)) / 2)

        def getWellCenter(position):
            x = bottom_left[0] + inset_x  + (well_size * position.column) + (well_size / 2)
            y = bottom_left[1] + height - inset_y - (well_size * position.row) - (well_size / 2)  
            return (x,y)
        
        
        txh = math.floor(well_radius * 1.3)
        canvas.setFont("Helvetica", txh)
        for i in range(plate.columns):
            label = str(i+1)
            txw = canvas.stringWidth(label)
            xpos = bottom_left[0] + inset_x + (i * well_size) + (well_size/2) - (txw/2)
            ypos = bottom_left[1] - (inset_y * 0.9) + height
            canvas.drawString(xpos, ypos, label)
        for i in range(plate.rows):
            label = "ABCDEFGH"[i]
            txw = canvas.stringWidth(label)
            xpos = bottom_left[0] + (inset_x * 0.9) - txw
            ypos = bottom_left[1] + height - inset_y - (i * well_size) - (well_size/2) - (txh/2)
            canvas.drawString(xpos, ypos, label)

        txh = well_radius *1.3
        canvas.setFont("Helvetica", txh)
        for well in plate.positions:
            label = str(plate[well.label].number) if plate[well.label] is not None else ''
            x,y = getWellCenter(well)            
            canvas.setFillColor(plate[well.label].project.color if plate[well.label] else 'white')
            canvas.circle(x, y, well_radius, stroke=1, fill=1)
            txw = canvas.stringWidth(label)
            cx = x - (txw/2)
            cy = y - (txh/2) * 0.9
            canvas.setFillColor('black')
            canvas.drawString(cx, cy, label)

        return