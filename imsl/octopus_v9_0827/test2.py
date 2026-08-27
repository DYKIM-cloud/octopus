# Assuming oceanoptics.py is in the same directory as this script
import matplotlib.pyplot as plt
from Hardware.UV.OceanOptics.oceanoptics import OceanOpticsSpectrometer

# Initialize the spectrometer
# Replace 'UV' with the appropriate spec_type for your spectrometer
spectrometer = OceanOpticsSpectrometer('UV')

# Set the integration time (in seconds)
new_integration_time = 0.0021  # 100 milliseconds
spectrometer.set_integration_time(new_integration_time)

# Print the current integration time
print(f"Current integration time: {spectrometer.integration_time} seconds")

# If you want to use the spectrometer to take measurements:
wavelengths, intensities = spectrometer.scan()
print(f"Wavelengths: {wavelengths}")
print(f"Intensities: {intensities}")

# Create a plot
plt.figure(figsize=(10, 6))
plt.plot(wavelengths, intensities)
plt.title('Spectrum Measurement')
plt.xlabel('Wavelength (nm)')
plt.ylabel('Intensity')
plt.grid(True)

# Add some annotations
plt.annotate(f'Integration Time: {spectrometer.integration_time}s', 
             xy=(0.05, 0.95), xycoords='axes fraction',
             fontsize=10, ha='left', va='top')

# Save the plot as a PNG file
plt.savefig('spectrum_plot.png')

# Display the plot
plt.show()

print("Graph has been saved as 'spectrum_plot.png'")

# If you want to print some of the data:
print(f"Wavelengths range: {wavelengths[0]} to {wavelengths[-1]} nm")
print(f"Max intensity: {max(intensities)}")