#!/usr/bin/env python
import matplotlib.pyplot as plt
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def read_in_masks(file_in):

    mask_file = np.load(file_in, allow_pickle=True)
    mask_data = mask_file.item()
    #print(mask_data)

    return mask_data


def make_mask_map(mask_data, RA_t, dec_t, d_t, date, file_out):

    filter_names = [['u', 'g', 'r'], ['i', 'z', 'y']]
    titles = ['Filter u','Filter g','Filter r','Filter i','Filter z','Filter y',]

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles = titles,
        specs=[[{"type": "image"}, {"type": "image"}, {"type": "image"}],
               [{"type": "image"}, {"type": "image"}, {"type": "image"}]],
        vertical_spacing=0.05
    )

    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            fig.add_trace(go.Heatmap(z=mask_data[filter_names[row-1][col-1]], 
                                     x=mask_data['ra'], 
                                     y=mask_data['dec'], 
                                     zmin=0, zmax=20,
                                     name=filter_names[row-1][col-1], 
                                     hovertemplate='RA: %{x}&deg;<br>Dec: %{y}&deg;<br>visits: %{z}<extra></extra>',
                                     colorbar=dict(outlinewidth=1, outlinecolor='black')
                                    ), 
                         row=row, col=col)
                
            fig.update_xaxes(range=[RA_t+d_t/2, RA_t-d_t/2], constrain='domain', 
                            row=row, col=col)
            fig.update_yaxes(range=[dec_t-d_t/2, dec_t+d_t/2], constrain='domain', 
                            scaleanchor=f"x{col + (row-1)*3}", 
                            scaleratio=1, row=row, col=col)
        
            fig.for_each_annotation(lambda a: a.update(font_size=24, y=a.y-0.006))

    fig.update_xaxes(
        showline=True, linewidth=1, linecolor='black', mirror=True,
        showgrid=False, zeroline=False
    )
    fig.update_yaxes(
        showline=True, linewidth=1, linecolor='black', mirror=True,
        showgrid=False, zeroline=False
    )

    fig.update_xaxes(title_text="RA (deg.)", row=2)
    fig.update_yaxes(title_text="Dec (deg.)", col=1)
    fig.update_layout(height=700, width=900, showlegend=True)
    fig.write_html(file_out)

    add_html_refresh(file_out)

    return


def add_html_refresh(file_in):

    with open(file_in, 'r') as file:
        lines = file.readlines()

    with open(file_in, 'w') as file:
        for line in lines:
            if line.startswith('<head>'):
                print('adding refresh to html')
                file.write(line.strip()+'\n'+'<head><meta http-equiv="refresh" content="5" /></head>'+'\n')
            else:
                file.write(line)

    return
