import json
import numpy as np
import matplotlib.pyplot as plt
from Analysis.AnalysisUV import smooth_Boxcar, getSpectrumArray
from Hardware.UV.OceanOptics.UV.QEPro2192 import QEPro2192
from Hardware.UV.OceanOptics.oceanoptics import OceanOpticsSpectrometer

def testuv(integration_time):
    ocean = OceanOpticsSpectrometer("UV", name="QEPro2192 UV Spectrometer")
    ocean.set_integration_time(integration_time)
    uv_obj = QEPro2192(integration_time=integration_time)
    raw_spectrum = uv_obj.obtain_reference_spectrum()
    spectrum_array = getSpectrumArray({'Wavelength': raw_spectrum.wavelengths.tolist(), 'RawSpectrum': raw_spectrum.intensities.tolist()})
    reference = smooth_Boxcar(spectrum_array, box_size=5)
    # Prepare results
    results = {
        'integration_time': uv_obj.integration_time,
        'Wavelength': reference[0].tolist(),
        'RawSpectrum': reference[1].tolist()
    }

    # Plot reference spectrum
    plt.figure(figsize=(10, 5))
    plt.plot(reference[0], reference[1])
    plt.title("Reference Spectrum")
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Intensity")
    plt.show()

if __name__ == "__main__":
    
    testuv(0.021)